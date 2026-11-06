"""Audit logs: an exact time window (since / until) – used for 'activity around this alert'."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import auth, new_user


def test_activity_in_a_time_window(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    user = new_user(client, new_email())  # registering + signing in are audited
    user_id = client.get("/api/users/me", headers=auth(user)).json()["id"]
    now = datetime.now(UTC)

    def window(since: datetime, until: datetime):
        return client.get(
            "/api/audit-logs/filter",
            params={"user_id": user_id, "since": since.isoformat(), "until": until.isoformat()},
            headers=auth(admin_token),
        )

    around = window(now - timedelta(minutes=30), now + timedelta(minutes=30))
    assert around.status_code == 200 and around.json()["total"] >= 1
    assert {item["user_id"] for item in around.json()["items"]} == {user_id}

    earlier = window(now - timedelta(hours=2), now - timedelta(hours=1))
    assert earlier.json()["total"] == 0

    backwards = window(now, now - timedelta(minutes=5))
    assert backwards.status_code == 400 and backwards.json()["error"]["code"] == "INVALID_RANGE"
