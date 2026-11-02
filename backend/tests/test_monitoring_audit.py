"""Milestone 3 – Tasks 1 & 2: activity monitoring and the tamper-evident audit log."""

import asyncio
import csv
import io
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from pymongo import AsyncMongoClient

from app.audit.service import AuditService
from app.core.config import get_settings
from tests.conftest import TEST_PASSWORD, update_share
from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, mongo_db, new_user, upload
from tests.test_shares import share

SECRET_NAME = "salary-slip-secret.pdf"


def user_id_of(client: TestClient, token: str) -> str:
    return client.get("/api/users/me", headers=auth(token)).json()["id"]


def activities(user_id: str) -> list[dict]:
    return list(mongo_db()["activity_logs"].find({"user_id": user_id}).sort("created_at", 1))


def audit_entries(user_id: str) -> list[dict]:
    collection = mongo_db()[get_settings().audit_collection]
    return list(collection.find({"user_id": user_id}).sort("seq", 1))


# ---------- Task 1: activities are recorded automatically ----------


def test_login_logout_and_failed_login_are_recorded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    token = new_user(client, email)
    client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})
    client.post("/api/auth/logout", headers=auth(token))

    uid = user_id_of(client, new_user(client, email))  # signs in again to look itself up
    kinds = [(a["action"], a["activity_type"], a["status"]) for a in activities(uid)]
    assert ("auth.login.success", "login", "success") in kinds
    assert ("auth.login.failed", "login", "failure") in kinds
    assert ("auth.logout", "logout", "success") in kinds


def test_file_activities_carry_file_id_and_type(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, SECRET_NAME, PDF).json()["id"]
    client.get(f"/api/files/{file_id}/download", headers=auth(token))
    client.get(f"/api/files/{file_id}/preview", headers=auth(token))
    share(client, token, file_id, permission="download")

    by_action = {a["action"]: a for a in activities(user_id_of(client, token))}
    assert by_action["file.upload"]["activity_type"] == "upload"
    assert by_action["file.download"]["activity_type"] == "download"
    assert by_action["file.preview"]["activity_type"] == "access"
    assert by_action["share.create"]["activity_type"] == "share"
    for action in ("file.upload", "file.download", "file.preview", "share.create"):
        assert by_action[action]["file_id"] == file_id
        assert by_action[action]["ip_address"] and by_action[action]["created_at"]


def test_unauthorized_attempts_are_recorded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    file_id = upload(client, owner, "private.pdf", PDF).json()["id"]
    intruder = new_user(client, new_email())

    assert client.get(f"/api/files/{file_id}/download", headers=auth(intruder)).status_code == 404
    assert client.get("/api/audit-logs", headers=auth(intruder)).status_code == 403

    records = activities(user_id_of(client, intruder))
    denied = [a for a in records if a["action"] == "file.access_denied"]
    assert denied and denied[0]["file_id"] == file_id and denied[0]["status"] == "failure"
    assert any(a["action"] == "auth.access_denied" for a in records)


def test_expired_and_revoked_link_attempts_are_recorded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "link.pdf", PDF).json()["id"]
    expired = share(client, token, file_id).json()
    revoked = share(client, token, file_id).json()
    update_share(expired["id"], expires_at=datetime.now(UTC) - timedelta(minutes=1))
    client.delete(f"/api/shares/{revoked['id']}", headers=auth(token))

    for created in (expired, revoked):
        client.get(f"/api/s/{created['url'].rsplit('/s/', 1)[1]}")

    reasons = {
        a["details"]["reason"]
        for a in mongo_db()["activity_logs"].find(
            {"action": "share.access_denied", "file_id": file_id}
        )
    }
    assert {"SHARE_EXPIRED", "SHARE_REVOKED"} <= reasons


# ---------- Task 2: audit log ----------


def test_audit_entries_have_the_brief_fields_and_no_file_names(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, SECRET_NAME, PDF).json()["id"]
    client.get(f"/api/files/{file_id}/download", headers=auth(token))

    entries = audit_entries(user_id_of(client, token))
    download = next(e for e in entries if e["action"] == "file.download")
    for field in ("log_id", "user_id", "username", "activity_type", "file_id", "description",
                  "status", "ip_address", "created_at", "seq", "prev_hash", "hash"):  # fmt: skip
        assert field in download
    assert download["file_id"] == file_id and download["username"] == "File User"
    assert download["description"] == "Downloaded a file (via owner)"
    assert "salary" not in str(entries)


def test_admin_audit_endpoints(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    token = new_user(client, new_email())
    uid = user_id_of(client, token)
    file_id = upload(client, token, SECRET_NAME, PDF).json()["id"]
    client.get(f"/api/files/{file_id}/download", headers=auth(token))
    admin = auth(admin_token)

    mine = client.get(f"/api/audit-logs/user/{uid}", headers=admin).json()
    of_file = client.get(f"/api/audit-logs/file/{file_id}", headers=admin).json()
    today = date.today().isoformat()
    filtered = client.get(
        "/api/audit-logs/filter",
        params={
            "user_id": uid,
            "activity_type": "download",
            "status": "success",
            "from": today,
            "to": today,
        },  # fmt: skip
        headers=admin,
    ).json()
    everything = client.get("/api/audit-logs", params={"limit": 5}, headers=admin).json()

    assert {e["action"] for e in mine["items"]} >= {"auth.login.success", "file.upload"}
    assert {e["action"] for e in of_file["items"]} == {"file.upload", "file.download"}
    assert [e["action"] for e in filtered["items"]] == ["file.download"]
    assert everything["total"] >= 3 and len(everything["items"]) <= 5
    assert SECRET_NAME not in str(mine) + str(of_file)
    assert client.get("/api/audit-logs/verify", headers=admin).json()["valid"] is True

    export = client.get("/api/audit-logs/export", params={"user_id": uid}, headers=admin)
    rows = list(csv.reader(io.StringIO(export.text.lstrip("﻿"))))
    assert rows[0][:3] == ["seq", "time_utc", "user_id"] and len(rows) >= 3


def test_regular_users_cannot_read_audit_logs(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    headers = auth(new_user(client, new_email()))
    for url in ("/api/audit-logs", "/api/audit-logs/filter", "/api/audit-logs/verify",
                "/api/audit-logs/export", "/api/activity-monitoring/activities"):  # fmt: skip
        assert client.get(url, headers=headers).status_code == 403


def _chain_service() -> tuple[AuditService, AsyncMongoClient, str]:
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongo_url, tz_aware=True)
    name = f"audit_chain_test_{uuid.uuid4().hex[:8]}"
    return AuditService(mongo[settings.mongo_db], collection=name), mongo, name


def _activity(n: int) -> dict:
    return {
        "action": "file.download",
        "user_id": "u1",
        "file_id": f"f{n}",
        "status": "success",
        "details": {"via": "owner"},
        "created_at": datetime.now(UTC),
    }


def test_chain_detects_changes_and_deletions() -> None:
    async def scenario() -> tuple:
        service, mongo, name = _chain_service()
        try:
            for n in range(4):
                await service.append(_activity(n), None)
            intact = await service.verify()
            await service.collection.update_one({"seq": 2}, {"$set": {"status": "failure"}})
            changed = await service.verify()
            await service.collection.update_one({"seq": 2}, {"$set": {"status": "success"}})
            restored = await service.verify()
            await service.collection.delete_one({"seq": 3})
            deleted = await service.verify()
            return intact, changed, restored, deleted
        finally:
            await mongo[get_settings().mongo_db].drop_collection(name)
            await mongo.close()

    intact, changed, restored, deleted = asyncio.run(scenario())
    assert intact.valid and intact.checked == 4
    assert not changed.valid and changed.broken_at_seq == 2 and "changed" in changed.reason
    assert restored.valid
    assert not deleted.valid and deleted.broken_at_seq == 3 and "missing" in deleted.reason


def test_simultaneous_writers_never_fork_the_chain() -> None:
    async def scenario():
        service, mongo, name = _chain_service()
        try:
            await asyncio.gather(*(service.append(_activity(n), None) for n in range(15)))
            return await service.verify()
        finally:
            await mongo[get_settings().mongo_db].drop_collection(name)
            await mongo.close()

    result = asyncio.run(scenario())
    assert result.valid and result.checked == 15


# ---------- admin activity monitoring ----------


def test_admin_activity_feed_and_summary_hide_file_names(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    token = new_user(client, new_email())
    uid = user_id_of(client, token)
    upload(client, token, SECRET_NAME, PDF)

    feed = client.get(
        "/api/activity-monitoring/activities", params={"user_id": uid}, headers=auth(admin_token)
    ).json()
    summary = client.get("/api/activity-monitoring/summary", headers=auth(admin_token)).json()
    old_viewer = client.get(
        "/api/admin/audit", params={"q": "file.upload"}, headers=auth(admin_token)
    ).json()

    assert {item["activity_type"] for item in feed["items"]} >= {"login", "upload"}
    assert SECRET_NAME not in str(feed) and SECRET_NAME not in str(old_viewer)
    assert summary["total"] > 0 and summary["active_users"] >= 1
    assert any(row["activity_type"] == "upload" for row in summary["by_type"])


def test_owner_still_sees_own_file_names(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    upload(client, token, SECRET_NAME, PDF)

    mine = client.get("/api/activity/me", headers=auth(token)).json()
    assert SECRET_NAME in str(mine)
    assert TEST_PASSWORD not in str(mine)
