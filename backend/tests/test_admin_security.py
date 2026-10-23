"""Admin Security Dashboard (Milestone 2, Phase 8): security events and admin-only reports."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import TEST_PASSWORD, clear_rate_limits, put_object, stored_object
from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, mongo_db, new_user, upload

ADMIN_URLS = [
    "/api/admin/security/overview",
    "/api/admin/security/logins",
    "/api/admin/security/events",
    "/api/admin/audit",
    "/api/admin/overview",
]


def events(**query) -> list[dict]:
    return list(mongo_db()["security_events"].find(query).sort("created_at", -1))


def login(client: TestClient, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ---------- RBAC: only admins ----------


@pytest.mark.parametrize("role", ["user", "guest"])
def test_non_admins_are_refused_by_the_backend(
    client: TestClient, new_email: Callable[[], str], role: str
) -> None:
    email = new_email()
    token = new_user(client, email, role=role)

    for url in ADMIN_URLS:
        response = client.get(url, headers=auth(token))
        assert response.status_code == 403, url

    denied = events(type="unauthorized_access", actor_email=email)
    assert len(denied) == len(ADMIN_URLS)
    assert denied[0]["details"]["path"] in ADMIN_URLS


def test_admin_sees_the_security_dashboard(client: TestClient, admin_token: str) -> None:  # noqa: F811
    data = client.get(
        "/api/admin/security/overview", params={"tz": "Asia/Kolkata"}, headers=auth(admin_token)
    ).json()

    assert set(data["metrics"]) == {
        "total_logins",
        "successful_logins",
        "failed_logins",
        "unauthorized_attempts",
        "security_events",
    }
    assert data["metrics"]["successful_logins"]["value"] >= 1  # the admin just logged in
    assert len(data["logins_by_day"]) == 30 and len(data["access_by_day"]) == 30
    assert data["recent_logins"][0]["status"] in ("success", "failed")


# ---------- events are recorded ----------


def test_failed_logins_then_lockout_raise_events(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    new_user(client, email)

    for _ in range(3):
        login(client, email, "Wrong!Passw0rd")
    after_three = events(actor_email=email)
    for _ in range(2):
        login(client, email, "Wrong!Passw0rd")
    login(client, email, TEST_PASSWORD)  # locked now

    types = [e["type"] for e in events(actor_email=email)]
    assert [e["type"] for e in after_three] == ["multiple_failed_logins"]
    assert "account_locked" in types and "blocked_request" in types
    locked = events(actor_email=email, type="account_locked")[0]
    assert locked["severity"] == "high" and locked["details"]["attempts"] == 5


def test_forged_token_is_recorded(client: TestClient) -> None:
    forged = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.bm90LWEtcmVhbC1zaWduYXR1cmU"
    before = len(events(type="unauthorized_access", message="Invalid or forged access token"))

    response = client.get("/api/files", headers=auth(forged))

    assert response.status_code == 401
    after = events(type="unauthorized_access", message="Invalid or forged access token")
    assert len(after) == before + 1


def test_disguised_and_disallowed_uploads_are_recorded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    token = new_user(client, email)

    upload(client, token, "report.pdf", b"MZ\x90\x00 this is really a program")
    upload(client, token, "tool.exe", b"MZ\x90\x00")

    threat = events(actor_email=email, type="file_threat")[0]
    assert threat["severity"] == "high" and threat["details"]["file_name"] == "report.pdf"
    assert events(actor_email=email, type="policy_violation")[0]["severity"] == "low"


def test_tampered_file_is_a_file_threat(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "report.pdf", PDF * 50).json()["id"]
    key = mongo_db()["files"].find_one({"_id": ObjectId(file_id)})["storage_key"]
    raw = bytearray(stored_object(key))
    raw[40] ^= 0xFF
    put_object(key, bytes(raw))

    client.get(f"/api/files/{file_id}/download", headers=auth(token))

    threat = events(type="file_threat", **{"details.file_id": file_id})
    assert threat and threat[0]["details"]["reason"] == "encrypted data failed its integrity check"


def test_sign_in_from_a_new_ip_is_recorded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    new_user(client, email)  # first sign-in (from "testclient")
    # Pretend all earlier sign-ins came from another address.
    mongo_db()["activity_logs"].update_many(
        {"actor_email": email, "action": "auth.login.success"},
        {"$set": {"ip_address": "10.1.2.3"}},
    )

    login(client, email, TEST_PASSWORD)

    assert events(actor_email=email, type="new_ip_login")


def test_rate_limit_is_recorded_once_per_minute(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    settings = get_settings()
    clear_rate_limits()
    settings.login_rate_limit_per_minute = 2
    since = datetime.now(UTC)
    try:
        codes = [login(client, new_email(), "Whatever!1").status_code for _ in range(5)]
    finally:
        settings.login_rate_limit_per_minute = 1000
        clear_rate_limits()

    assert codes[-1] == 429
    blocked = events(type="blocked_request", created_at={"$gte": since})
    assert len([e for e in blocked if e["details"].get("scope") == "login"]) == 1


def test_admin_actions_are_recorded(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    email = new_email()
    new_user(client, email)
    user_id = client.get(
        "/api/admin/users", params={"search": email}, headers=auth(admin_token)
    ).json()["items"][0]["id"]

    client.patch(f"/api/admin/users/{user_id}", json={"role": "guest"}, headers=auth(admin_token))

    event = events(type="admin_action", message=f"Changed account {email}")[0]
    assert event["severity"] == "info"


# ---------- reports ----------


def test_login_history_and_audit_search(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    ghost = new_email()
    login(client, ghost, "Wrong!Passw0rd")  # no such account

    failed = client.get(
        "/api/admin/security/logins", params={"status": "failed"}, headers=auth(admin_token)
    ).json()["items"]
    audit = client.get("/api/admin/audit", params={"q": ghost}, headers=auth(admin_token)).json()

    entry = next(e for e in failed if e["email"] == ghost)
    assert entry["user_name"] is None and entry["reason"] == "unknown_email"
    assert entry["location"] == "Unknown"  # the test client has no real IP
    assert audit["total"] == 1 and audit["items"][0]["action"] == "auth.login.failed"


def test_system_overview_shows_sizes_but_no_file_names(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    email = new_email()
    token = new_user(client, email)
    upload(client, token, "very-private-name.pdf", PDF)

    response = client.get("/api/admin/overview", headers=auth(admin_token))

    data = response.json()
    mine = next(u for u in data["storage_by_user"] if u["email"] == email)
    assert mine["files"] == 1 and mine["bytes"] == len(PDF)
    assert "very-private-name" not in response.text
    assert data["users"]["total"] >= 2 and data["keys"]["active_version"] >= 1
    assert len(data["activity_by_day"]) == 30
