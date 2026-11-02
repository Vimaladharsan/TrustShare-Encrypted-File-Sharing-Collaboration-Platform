"""Milestone 3 – Task 3: notifications, security alerts, expiry reminders, email and live stream."""

import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.mongo import get_mongo
from app.db.redis import get_redis
from app.notifications.models import channel
from app.notifications.scheduler import run_once
from app.notifications.service import NotificationService, load_user
from app.notifications.stream import event_stream
from tests.conftest import clear_rate_limits, update_share
from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, mongo_db, new_user, upload
from tests.test_shares import share


@pytest.fixture(autouse=True)
def fresh_throttles() -> Iterator[None]:
    clear_rate_limits()  # also clears detection windows and notification throttles
    yield
    clear_rate_limits()


def me(client: TestClient, token: str) -> dict:
    return client.get("/api/users/me", headers=auth(token)).json()


def notifications(client: TestClient, token: str, **params) -> dict:
    return client.get("/api/notifications", params=params, headers=auth(token)).json()


def share_with(client: TestClient, owner: str, file_id: str, email: str, **body) -> dict:
    response = share(client, owner, file_id, share_type="user", recipient_email=email, **body)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- file sharing & downloads ----------


def test_direct_share_notifies_the_recipient_in_app_and_by_email(
    client: TestClient, new_email: Callable[[], str], outbox
) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    file_id = upload(client, owner, "budget.pdf", PDF).json()["id"]

    share_with(client, owner, file_id, recipient_email, permission="download")

    page = notifications(client, recipient)
    assert page["unread"] == 1
    item = page["items"][0]
    assert item["type"] == "file_shared" and "budget.pdf" in item["message"]
    assert "File User" in item["message"] and item["link"] == "/shared-with-me"
    assert any(m.to == recipient_email and "budget.pdf" in m.subject for m in outbox.sent)

    read = client.post(f"/api/notifications/{item['id']}/read", headers=auth(recipient)).json()
    assert read["read"] is True
    assert client.get("/api/notifications/unread-count", headers=auth(recipient)).json() == {
        "unread": 0
    }


def test_owner_is_told_when_a_shared_file_is_downloaded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    file_id = upload(client, owner, "photo.pdf", PDF).json()["id"]
    received = share_with(client, owner, file_id, recipient_email, permission="download")

    for _ in range(2):  # the second one falls inside the cooldown – no second notice
        client.get(f"/api/shares/{received['id']}/download", headers=auth(recipient))
    client.get(f"/api/files/{file_id}/download", headers=auth(owner))  # owner: no notice

    downloads = notifications(client, owner, type="file_downloaded")
    assert downloads["total"] == 1
    assert "photo.pdf" in downloads["items"][0]["message"]
    assert "UTC" in downloads["items"][0]["message"]  # includes the download time


def test_link_download_notice_names_an_anonymous_visitor(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    file_id = upload(client, owner, "public.pdf", PDF).json()["id"]
    link = share(client, owner, file_id, permission="download").json()["url"].rsplit("/s/", 1)[1]

    client.get(f"/api/s/{link}/download")

    item = notifications(client, owner, type="file_downloaded")["items"][0]
    assert item["message"].startswith("Someone with the share link downloaded")


# ---------- security alerts ----------


def test_suspicious_activity_alerts_admins_and_the_user(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
    outbox,
) -> None:
    email = new_email()
    token = new_user(client, email)
    for _ in range(6):
        client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})

    alerts = notifications(client, admin_token, type="security_alert")["items"]
    brute_force = [a for a in alerts if a["data"].get("event_type") == "repeated_failed_logins"]
    assert brute_force and brute_force[0]["severity"] == "critical"
    assert brute_force[0]["link"] == "/admin/security"
    admin_email = me(client, admin_token)["email"]
    assert any(m.to == admin_email and "Security alert" in m.subject for m in outbox.sent)

    # The account is locked now, but the access token from before the attack still works.
    own = notifications(client, token, type="account_security")["items"]
    titles = {n["title"] for n in own}
    assert "Many failed sign-ins on your account" in titles
    assert "Your account was locked" in titles


def test_low_severity_events_do_not_ping_admins(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    token = new_user(client, new_email())
    before = notifications(client, admin_token, type="security_alert")["total"]
    upload(client, token, "tool.exe", b"MZ\x90\x00")  # policy_violation = low

    assert notifications(client, admin_token, type="security_alert")["total"] == before


# ---------- preferences ----------


def test_preferences_turn_email_off(
    client: TestClient,
    new_email: Callable[[], str],
    outbox,
    admin_token: str,  # noqa: F811
) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    defaults = client.get("/api/notifications/preferences", headers=auth(recipient)).json()
    by_type = {item["type"]: item for item in defaults["items"]}
    assert by_type["file_shared"]["email"] is True and by_type["file_downloaded"]["email"] is False
    assert "security_alert" not in by_type  # only admins get security alerts
    admin_types = client.get("/api/notifications/preferences", headers=auth(admin_token)).json()
    assert "security_alert" in {item["type"] for item in admin_types["items"]}

    updated = client.put(
        "/api/notifications/preferences",
        json={"email": {"file_shared": False}},
        headers=auth(recipient),
    ).json()
    assert {i["type"]: i["email"] for i in updated["items"]}["file_shared"] is False
    file_id = upload(client, owner, "quiet.pdf", PDF).json()["id"]
    share_with(client, owner, file_id, recipient_email)

    assert notifications(client, recipient)["total"] == 1  # still in the app
    assert not [m for m in outbox.sent if m.to == recipient_email and "shared" in m.subject]
    bad = client.put(
        "/api/notifications/preferences", json={"email": {"spam": True}}, headers=auth(recipient)
    )
    assert bad.status_code == 400


def test_mark_all_read(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    for name in ("a.pdf", "b.pdf"):
        file_id = upload(client, owner, name, PDF + name.encode()).json()["id"]
        share_with(client, owner, file_id, recipient_email)

    assert client.post("/api/notifications/read-all", headers=auth(recipient)).json() == {
        "updated": 2
    }
    assert notifications(client, recipient, unread=True)["total"] == 0
    other = new_user(client, new_email())
    item_id = notifications(client, recipient)["items"][0]["id"]
    assert client.post(f"/api/notifications/{item_id}/read", headers=auth(other)).status_code == 404


# ---------- background job: expiry reminders and expired links ----------


def test_expiry_reminder_and_expired_link(
    client: TestClient, new_email: Callable[[], str], outbox
) -> None:
    owner_email = new_email()
    owner = new_user(client, owner_email)
    file_id = upload(client, owner, "deadline.pdf", PDF).json()["id"]
    soon = share(client, owner, file_id, expires_at=(datetime.now(UTC) + timedelta(hours=2))
                 .isoformat()).json()  # fmt: skip
    old = share(client, owner, file_id).json()
    revoked = share(client, owner, file_id).json()
    update_share(old["id"], expires_at=datetime.now(UTC) - timedelta(minutes=5))
    update_share(revoked["id"], expires_at=datetime.now(UTC) - timedelta(minutes=5))
    client.delete(f"/api/shares/{revoked['id']}", headers=auth(owner))

    first = client.portal.call(run_once)
    second = client.portal.call(run_once)  # nothing is sent twice

    assert first["reminders"] >= 1 and first["expired"] >= 1
    assert second == {"reminders": 0, "expired": 0}
    reminders = notifications(client, owner, type="link_expiring")["items"]
    assert len(reminders) == 1 and "deadline.pdf" in reminders[0]["message"]
    assert reminders[0]["data"]["share_id"] == soon["id"]
    assert any(m.to == owner_email and "about to expire" in m.subject for m in outbox.sent)
    expired = notifications(client, owner, type="link_expired")["items"]
    assert [n["data"]["share_id"] for n in expired] == [old["id"]]  # not the revoked one
    record = mongo_db()["activity_logs"].find_one({"action": "share.expired", "file_id": file_id})
    assert record is not None and record["details"]["share_id"] == old["id"]


# ---------- live stream (Server-Sent Events) ----------


def test_stream_requires_login_and_sends_ready(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    assert client.get("/api/notifications/stream").status_code == 401
    token = new_user(client, new_email())
    settings = get_settings()
    saved, settings.sse_max_seconds = settings.sse_max_seconds, 1  # short stream for the test
    try:
        with client.stream("GET", "/api/notifications/stream", headers=auth(token)) as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            body = "".join(response.iter_text())
    finally:
        settings.sse_max_seconds = saved
    assert 'event: ready\ndata: {"unread": 0}' in body
    assert "event: reconnect" in body


def test_stream_delivers_new_notifications_instantly(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    user_id = me(client, new_user(client, new_email()))["id"]

    async def scenario() -> list[str]:
        payload = {"sub": user_id, "exp": time.time() + 60, "jti": "test", "iat": time.time()}
        stream = event_stream(None, get_redis(), channel(user_id), payload, {"unread": 0})
        ready = await anext(stream)
        user = await load_user(user_id)
        await NotificationService(get_mongo(), get_redis()).notify(
            user, "link_expired", "Live!", "Delivered through Redis pub/sub."
        )
        live = await anext(stream)
        await stream.aclose()
        return [ready, live]

    ready, live = client.portal.call(scenario)
    assert ready.startswith("event: ready")
    assert live.startswith("event: notification") and '"title": "Live!"' in live


def test_stream_asks_to_reauthenticate_when_the_token_expires(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    user_id = me(client, new_user(client, new_email()))["id"]

    async def scenario() -> list[str]:
        payload = {"sub": user_id, "exp": time.time() - 1, "jti": "x", "iat": time.time() - 900}
        return [chunk async for chunk in event_stream(None, get_redis(), channel(user_id),
                                                       payload, {"unread": 0})]  # fmt: skip

    events = client.portal.call(scenario)
    assert events[0].startswith("event: ready") and events[-1].startswith("event: reauth")


# ---------- admin: notification management ----------


def test_admin_delivery_stats_without_message_text(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    new_user(client, recipient_email)
    file_id = upload(client, owner, "top-secret-name.pdf", PDF).json()["id"]
    share_with(client, owner, file_id, recipient_email)

    stats = client.get("/api/notifications/admin/stats", headers=auth(admin_token))
    assert stats.status_code == 200
    data = stats.json()
    assert data["total"] >= 1 and any(t["type"] == "file_shared" for t in data["by_type"])
    assert any(d["recipient_email"] == recipient_email for d in data["recent"])
    assert "top-secret-name" not in stats.text
    assert client.get("/api/notifications/admin/stats", headers=auth(owner)).status_code == 403
