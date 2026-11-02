"""Milestone 3 – final integration: the brief's end-to-end workflow in one test.

1 register + log in · 2 upload · 3 encrypted and stored · 4 share with another user ·
5 download the shared file · 6 activity logs and notifications · 7 suspicious activity ·
8 log in as admin · 9 reports, analytics, audit logs and alerts show it all.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import file_key_row, stored_object
from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, mongo_db, new_user, upload


def test_milestone_3_end_to_end(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811 – step 8: the administrator
    outbox,
) -> None:
    # 1. register and log in
    owner_email, recipient_email = new_email(), new_email()
    owner, recipient = new_user(client, owner_email), new_user(client, recipient_email)
    owner_id = client.get("/api/users/me", headers=auth(owner)).json()["id"]

    # 2-3. upload → encrypted with its own key, ciphertext in object storage
    file_id = upload(client, owner, "e2e-plan.pdf", PDF).json()["id"]
    doc = mongo_db()["files"].find_one({"original_name": "e2e-plan.pdf", "owner_id": owner_id})
    assert stored_object(doc["storage_key"]).startswith(b"TSE1")
    assert file_key_row(file_id) is not None

    # 4. share with another user → in-app notification + email
    share = client.post(
        f"/api/files/{file_id}/shares",
        json={"share_type": "user", "recipient_email": recipient_email, "permission": "download"},
        headers=auth(owner),
    ).json()
    shared = client.get("/api/notifications", headers=auth(recipient)).json()["items"]
    assert shared[0]["type"] == "file_shared" and "e2e-plan.pdf" in shared[0]["message"]
    assert any(m.to == recipient_email for m in outbox.sent)

    # 5. download the shared file → the original bytes; the owner is told
    assert client.get(f"/api/shares/{share['id']}/download", headers=auth(recipient)).content == PDF
    told = client.get("/api/notifications", params={"type": "file_downloaded"}, headers=auth(owner))
    assert told.json()["total"] == 1

    # 6. activity logs: every step recorded automatically
    actions = {
        a["action"]
        for a in client.get("/api/activity/me", params={"limit": 50}, headers=auth(owner)).json()[
            "items"
        ]
    }
    assert {"auth.login.success", "file.upload", "share.create"} <= actions

    # 7. suspicious activity: brute force against the recipient
    for _ in range(6):
        client.post("/api/auth/login", json={"email": recipient_email, "password": "wrong-Pass0!"})

    # 8-9. the administrator sees everything – without file names
    admin = auth(admin_token)
    audit = client.get(f"/api/audit-logs/file/{file_id}", headers=admin)
    assert {e["action"] for e in audit.json()["items"]} >= {"file.upload", "file.download"}
    assert client.get("/api/audit-logs/verify", headers=admin).json()["valid"] is True
    alerts = client.get(
        "/api/security-monitoring/events",
        params={"user": recipient_email, "type": "repeated_failed_logins"},
        headers=admin,
    ).json()
    assert alerts["total"] == 1 and alerts["items"][0]["severity"] == "high"
    admin_alerts = client.get(
        "/api/notifications", params={"type": "security_alert"}, headers=admin
    ).json()
    assert admin_alerts["total"] >= 1
    uploads = client.get("/api/reports/uploads", params={"user_id": owner_id}, headers=admin)
    sharing = client.get("/api/reports/sharing", params={"user_id": owner_id}, headers=admin)
    storage = client.get("/api/analytics/storage", params={"user_id": owner_id}, headers=admin)
    assert uploads.json()["summary"]["uploaded"] == 1
    assert sharing.json()["summary"]["direct"] == 1
    assert storage.json()["total_files"] == 1 and storage.json()["total_bytes"] == len(PDF)
    for response in (audit, uploads, sharing, storage):
        assert "e2e-plan" not in response.text  # privacy: admins never see file names
