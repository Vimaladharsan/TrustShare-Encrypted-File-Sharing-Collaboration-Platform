"""Milestone 3 – Task 6: rule-based suspicious activity detection and the alert workflow.

Covers the brief's five test scenarios: repeated wrong passwords, file access without permission,
repeated downloads, expired links and revoked links.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import clear_rate_limits, update_share
from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, mongo_db, new_user, upload
from tests.test_shares import share


@pytest.fixture(autouse=True)
def fresh_windows() -> Iterator[None]:
    """Each test starts with empty detection windows and the default thresholds."""
    settings = get_settings()
    saved = settings.detect_downloads_limit
    clear_rate_limits()  # also clears detect:* and detect_cooldown:* keys
    yield
    settings.detect_downloads_limit = saved
    clear_rate_limits()


def alerts(event_type: str, since: datetime, **query) -> list[dict]:
    match = {"type": event_type, "created_at": {"$gte": since}, **query}
    return list(mongo_db()["security_events"].find(match))


def user_id_of(client: TestClient, token: str) -> str:
    return client.get("/api/users/me", headers=auth(token)).json()["id"]


def link_token(created: dict) -> str:
    return created["url"].rsplit("/s/", 1)[1]


# ---------- the five scenarios ----------


def test_repeated_wrong_passwords_raise_one_high_alert(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    uid = user_id_of(client, new_user(client, email))
    start = datetime.now(UTC)

    for _ in range(6):  # more than 5 within 10 minutes (the 6th hits the lockout)
        client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})
    found = alerts("repeated_failed_logins", start, user_id=uid)
    for _ in range(3):  # still attacking – no flood of alerts (one per window)
        client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})

    assert len(found) == 1
    alert = found[0]
    assert alert["severity"] == "high" and alert["status"] == "open" and alert["alert_id"]
    assert alert["rule"]["count"] == 6 and alert["rule"]["window_minutes"] == 10
    assert len(alerts("repeated_failed_logins", start, user_id=uid)) == 1


def test_repeated_access_without_permission(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    file_id = upload(client, owner, "private.pdf", PDF).json()["id"]
    intruder = new_user(client, new_email())
    uid = user_id_of(client, intruder)
    start = datetime.now(UTC)

    for _ in range(4):
        client.get(f"/api/files/{file_id}/download", headers=auth(intruder))
    assert alerts("repeated_unauthorized_access", start, user_id=uid) == []
    client.get(f"/api/files/{file_id}/download", headers=auth(intruder))  # the 5th

    found = alerts("repeated_unauthorized_access", start, user_id=uid)
    assert len(found) == 1 and found[0]["severity"] == "high"


def test_too_many_downloads_in_a_short_time(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    get_settings().detect_downloads_limit = 3  # small limit for the test (default 20 / 5 min)
    token = new_user(client, new_email())
    uid = user_id_of(client, token)
    file_id = upload(client, token, "popular.pdf", PDF).json()["id"]
    start = datetime.now(UTC)

    for _ in range(4):
        client.get(f"/api/files/{file_id}/download", headers=auth(token))

    found = alerts("excessive_downloads", start, user_id=uid)
    assert len(found) == 1 and found[0]["severity"] == "medium"
    assert found[0]["rule"]["limit"] == 3


def test_repeated_use_of_expired_and_revoked_links(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "link.pdf", PDF).json()["id"]
    expired, revoked = share(client, token, file_id).json(), share(client, token, file_id).json()
    update_share(expired["id"], expires_at=datetime.now(UTC) - timedelta(minutes=1))
    client.delete(f"/api/shares/{revoked['id']}", headers=auth(token))
    start = datetime.now(UTC)

    for _ in range(3):
        client.get(f"/api/s/{link_token(expired)}")
        client.get(f"/api/s/{link_token(revoked)}")

    assert len(alerts("expired_link_abuse", start)) == 1
    assert len(alerts("revoked_link_abuse", start)) == 1


# ---------- admin: monitoring section and alert workflow ----------


def test_admin_summary_events_filters_and_rules(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    email = new_email()
    new_user(client, email)
    for _ in range(6):
        client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})
    admin = auth(admin_token)

    summary = client.get("/api/security-monitoring/summary", headers=admin).json()
    page = client.get(
        "/api/security-monitoring/events",
        params={
            "user": email,
            "type": "repeated_failed_logins",
            "severity": "high",
            "status": "open",
        },  # fmt: skip
        headers=admin,
    ).json()
    rules = client.get("/api/security-monitoring/rules", headers=admin).json()

    assert summary["failed_logins"] >= 6 and summary["open_alerts"] >= 1
    assert any(t["type"] == "repeated_failed_logins" for t in summary["alerts_by_type"])
    assert page["total"] == 1 and page["items"][0]["title"].startswith("Repeated failed sign-ins")
    assert {r["name"] for r in rules} == {
        "repeated_failed_logins",
        "repeated_unauthorized_access",
        "excessive_downloads",
        "expired_link_abuse",
        "revoked_link_abuse",
    }
    assert next(r for r in rules if r["name"] == "excessive_downloads")["condition"] == (
        "more than 20 within 5 min"
    )


def test_alert_workflow_acknowledge_resolve_reopen(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    email = new_email()
    new_user(client, email)
    for _ in range(6):
        client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})
    admin = auth(admin_token)
    alert = client.get(
        "/api/security-monitoring/events", params={"user": email}, headers=admin
    ).json()["items"][0]
    url = f"/api/security-monitoring/events/{alert['id']}"

    acknowledged = client.patch(url, json={"action": "acknowledge"}, headers=admin).json()
    resolved = client.patch(
        url, json={"action": "resolve", "note": "User forgot the password"}, headers=admin
    ).json()
    resolved_list = client.get(
        "/api/security-monitoring/events", params={"user": email, "status": "resolved"},
        headers=admin,
    ).json()  # fmt: skip
    reopened = client.patch(url, json={"action": "reopen"}, headers=admin).json()

    assert acknowledged["status"] == "acknowledged" and acknowledged["acknowledged_by"]
    assert resolved["status"] == "resolved" and resolved["note"] == "User forgot the password"
    assert resolved_list["total"] == 1
    assert reopened["status"] == "open" and reopened["resolved_by"] is None
    audit = mongo_db()[get_settings().audit_collection]
    assert audit.find_one({"action": "admin.alert_resolved"}) is not None
    bad = client.patch(url, json={"action": "delete"}, headers=admin)
    missing = client.patch(
        "/api/security-monitoring/events/000000000000000000000000",
        json={"action": "resolve"},
        headers=admin,
    )
    assert bad.status_code == 422 and missing.status_code == 404


def test_alerts_hide_file_names_and_users_are_blocked(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    email = new_email()
    token = new_user(client, email)
    upload(client, token, "secret-plan.pdf", b"MZ\x90\x00 really a program")  # file threat

    page = client.get(
        "/api/security-monitoring/events", params={"user": email}, headers=auth(admin_token)
    ).json()
    assert page["total"] >= 1 and "secret-plan" not in str(page)
    for url in ("/api/security-monitoring/summary", "/api/security-monitoring/events",
                "/api/security-monitoring/rules"):  # fmt: skip
        assert client.get(url, headers=auth(token)).status_code == 403
