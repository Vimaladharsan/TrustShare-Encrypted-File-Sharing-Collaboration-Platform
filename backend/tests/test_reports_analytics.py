"""Milestone 3 – Tasks 4 & 5: reports and storage analytics match the real records exactly."""

import csv
import io
from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.conftest import clear_rate_limits
from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, new_user, upload
from tests.test_shares import share

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SECRET = "confidential-merger"


@pytest.fixture
def scenario(client: TestClient, new_email: Callable[[], str]) -> dict:
    """One owner: 2 uploads (pdf + png), 1 rejected, 2 own downloads, a link and a direct share
    whose recipient downloads once; one intruder tries the owner's file."""
    clear_rate_limits()
    owner = new_user(client, new_email())
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    intruder = new_user(client, new_email())
    pdf_id = upload(client, owner, f"{SECRET}.pdf", PDF).json()["id"]
    png_id = upload(client, owner, f"{SECRET}-chart.png", PNG).json()["id"]
    upload(client, owner, f"{SECRET}.exe", b"MZ\x90\x00")  # rejected
    for _ in range(2):
        client.get(f"/api/files/{pdf_id}/download", headers=auth(owner))
    share(client, owner, pdf_id, permission="download")
    direct = share(
        client, owner, png_id, share_type="user", recipient_email=recipient_email,
        permission="download",
    ).json()  # fmt: skip
    client.get(f"/api/shares/{direct['id']}/download", headers=auth(recipient))
    client.get(f"/api/files/{pdf_id}/download", headers=auth(intruder))  # denied

    def uid(token: str) -> str:
        return client.get("/api/users/me", headers=auth(token)).json()["id"]

    return {
        "owner": uid(owner),
        "recipient": uid(recipient),
        "recipient_email": recipient_email,
        "intruder": uid(intruder),
        "pdf": pdf_id,
        "png": png_id,
        "owner_token": owner,
    }


def get(client: TestClient, token: str, url: str, **params):
    response = client.get(url, params=params, headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()


# ---------- Task 5: storage analytics ----------


def test_storage_and_user_storage(
    client: TestClient,
    scenario: dict,
    admin_token: str,  # noqa: F811
) -> None:
    uid = scenario["owner"]
    storage = get(client, admin_token, "/api/analytics/storage", user_id=uid)
    images = get(client, admin_token, "/api/analytics/storage", user_id=uid, file_type="image")
    users = get(client, admin_token, "/api/analytics/users/storage", user_id=uid)

    assert storage["total_files"] == 2 and storage["total_bytes"] == len(PDF) + len(PNG)
    categories = {c["category"]: c for c in storage["by_category"]}
    assert categories["document"]["files"] == 1 and categories["image"]["bytes"] == len(PNG)
    assert images["total_files"] == 1
    assert len(users["items"]) == 1
    row = users["items"][0]
    assert row["files"] == 2 and row["bytes"] == len(PDF) + len(PNG) and row["quota_bytes"]
    assert row["last_upload_at"] is not None


def test_file_download_and_sharing_statistics(
    client: TestClient,
    scenario: dict,
    admin_token: str,  # noqa: F811
) -> None:
    owner, today = scenario["owner"], date.today().isoformat()
    files = get(client, admin_token, "/api/analytics/files", user_id=owner, **{"from": today})
    own = get(client, admin_token, "/api/analytics/downloads", user_id=owner)
    received = get(client, admin_token, "/api/analytics/downloads", user_id=scenario["recipient"])
    sharing = get(client, admin_token, "/api/analytics/sharing", user_id=owner)

    assert files["uploaded"] == 2 and files["rejected_uploads"] == 1
    assert files["shared_files"] == 2  # only this user's shares
    day = files["uploads_by_day"][-1]
    assert day["document"] == 1 and day["image"] == 1
    assert own["total"] == 2 and own["by_owner"] == 2
    assert own["most_downloaded"][0]["file_id"] == scenario["pdf"]
    assert own["most_downloaded"][0]["extension"] == "pdf"
    assert received["via_direct_share"] == 1 and received["unique_users"] == 1
    assert sharing["created"] == 2 and sharing["link_shares"] == 1 and sharing["direct_shares"] == 1
    assert sharing["active"] == 2
    assert sharing["top_recipients"][0]["email"] == scenario["recipient_email"]


# ---------- Task 4: reports ----------


def test_upload_and_download_reports(
    client: TestClient,
    scenario: dict,
    admin_token: str,  # noqa: F811
) -> None:
    uploads = client.get(
        "/api/reports/uploads", params={"user_id": scenario["owner"]}, headers=auth(admin_token)
    )
    report = uploads.json()
    assert report["summary"]["uploaded"] == 2 and report["summary"]["rejected"] == 1
    assert {row["file_type"] for row in report["rows"]} == {"pdf", "png", "exe"}
    assert {r["reason"] for r in report["breakdowns"]["rejected_by_reason"]} == {
        "UNSUPPORTED_FILE_TYPE"
    }
    assert SECRET not in uploads.text  # file IDs and types only

    downloads = get(client, admin_token, "/api/reports/downloads", user_id=scenario["owner"])
    assert downloads["summary"]["downloads"] == 2
    denied = get(client, admin_token, "/api/reports/downloads", user_id=scenario["intruder"])
    assert denied["summary"]["failed_attempts"] == 1
    assert denied["rows"][0]["reason"] == "NOT_YOUR_FILE"

    exported = client.get(
        "/api/reports/uploads",
        params={"user_id": scenario["owner"], "format": "csv"},
        headers=auth(admin_token),
    )
    rows = list(csv.reader(io.StringIO(exported.text.lstrip("﻿"))))
    assert exported.headers["content-type"].startswith("text/csv")
    assert rows[0][:3] == ["time", "user_email", "user_id"] and len(rows) == 4


def test_sharing_user_activity_and_security_reports(
    client: TestClient,
    scenario: dict,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    sharing = get(client, admin_token, "/api/reports/sharing", user_id=scenario["owner"])
    assert sharing["summary"]["shares"] == 2 and sharing["summary"]["active"] == 2
    assert {r["recipient_email"] for r in sharing["rows"]} == {scenario["recipient_email"], None}

    activity = client.get(f"/api/reports/users/{scenario['owner']}", headers=auth(admin_token))
    data = activity.json()
    assert data["summary"]["uploads"] >= 3 and data["summary"]["downloads"] == 2
    assert data["summary"]["shares"] == 2 and SECRET not in activity.text
    assert any(row["description"].startswith("Uploaded a file (") for row in data["rows"])
    missing = client.get(
        "/api/reports/users/00000000-0000-0000-0000-000000000000", headers=auth(admin_token)
    )
    assert missing.status_code == 404

    email = new_email()
    new_user(client, email)
    for _ in range(6):
        client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})
    security = get(client, admin_token, "/api/reports/security")
    assert security["summary"]["failed_logins"] >= 6 and security["summary"]["high_alerts"] >= 1
    assert any(r["type"] == "repeated_failed_logins" for r in security["rows"])


def test_reports_and_analytics_are_admin_only(client: TestClient, scenario: dict) -> None:
    token = scenario["owner_token"]
    for url in ("/api/analytics/storage", "/api/analytics/users/storage", "/api/analytics/files",
                "/api/analytics/downloads", "/api/analytics/sharing", "/api/reports/uploads",
                "/api/reports/downloads", "/api/reports/sharing", "/api/reports/security",
                f"/api/reports/users/{scenario['owner']}"):  # fmt: skip
        assert client.get(url, headers=auth(token)).status_code == 403, url
    assert client.get("/api/analytics/me", headers=auth(token)).status_code == 200  # own analytics
