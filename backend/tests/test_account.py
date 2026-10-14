"""Change password, log out of all devices, and login history in the activity log."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.config import get_settings
from tests.conftest import TEST_PASSWORD
from tests.test_auth import auth, login_token, register

NEW_PASSWORD = "Chang3d!Passw0rd"


def change(client: TestClient, token: str, current: str, new: str):
    return client.post(
        "/api/users/me/password",
        json={"current_password": current, "new_password": new},
        headers=auth(token),
    )


def actions_for(email: str) -> list[dict]:
    """Activity-log entries about this account (newest last)."""
    settings = get_settings()
    mongo = MongoClient(settings.mongo_url)
    try:
        logs = mongo[settings.mongo_db]["activity_logs"]
        query = {"$or": [{"actor_email": email}, {"details.email": email}]}
        return list(logs.find(query).sort("created_at", 1))
    finally:
        mongo.close()


# ---------- change password ----------


def test_change_password_keeps_this_device_and_logs_out_the_others(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)
    other_device = login_token(client, email)
    this_device = login_token(client, email)

    response = change(client, this_device, TEST_PASSWORD, NEW_PASSWORD)

    assert response.status_code == 200
    new_token = response.json()["access_token"]
    assert client.get("/api/users/me", headers=auth(new_token)).status_code == 200
    assert client.get("/api/users/me", headers=auth(other_device)).status_code == 401
    old = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert old.status_code == 401
    assert login_token(client, email, NEW_PASSWORD)


def test_wrong_current_password_is_rejected(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)

    response = change(client, login_token(client, email), "Wr0ng!Password", NEW_PASSWORD)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WRONG_PASSWORD"


def test_new_password_must_differ_and_follow_the_rules(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)
    token = login_token(client, email)

    same = change(client, token, TEST_PASSWORD, TEST_PASSWORD)
    weak = change(client, token, TEST_PASSWORD, "nouppercase1!")

    assert same.json()["error"]["code"] == "SAME_PASSWORD"
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"


# ---------- log out of all devices ----------


def test_logout_all_is_recorded(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    register(client, email)

    response = client.post("/api/auth/logout-all", headers=auth(login_token(client, email)))

    assert response.status_code == 204
    assert "auth.logout_all" in [log["action"] for log in actions_for(email)]


# ---------- login history ----------


def test_successful_and_failed_logins_are_recorded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)

    client.post("/api/auth/login", json={"email": email, "password": "Wr0ng!Password"})
    login_token(client, email)

    logs = actions_for(email)
    failed = next(log for log in logs if log["action"] == "auth.login.failed")
    success = next(log for log in logs if log["action"] == "auth.login.success")
    assert failed["status"] == "failure"
    assert failed["details"]["reason"] == "wrong_password"
    assert success["details"]["method"] == "password"
    assert success["ip_address"]  # who, what, when – and from where


def test_attempts_on_unknown_emails_are_recorded(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()  # never registered

    client.post("/api/auth/login", json={"email": email, "password": "Wr0ng!Password"})

    log = next(log for log in actions_for(email) if log["action"] == "auth.login.failed")
    assert log["user_id"] is None
    assert log["details"]["reason"] == "unknown_email"


def test_lockout_is_recorded(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    register(client, email)

    for _ in range(6):  # 5 wrong passwords lock the account; the 6th attempt is refused
        client.post("/api/auth/login", json={"email": email, "password": "Wr0ng!Password"})

    assert "auth.login.locked" in [log["action"] for log in actions_for(email)]
