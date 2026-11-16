"""New-device sign-in alert: a sign-in from a browser + system the account never used before
is recorded as a security event and the owner is notified (in the app and by email)."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD, clear_rate_limits
from tests.test_files import mongo_db, new_user

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
CHROME_WINDOWS_UPDATED = CHROME_WINDOWS.replace("131.0.0.0", "132.0.0.0")


def sign_in(client: TestClient, email: str, user_agent: str | None = None) -> None:
    headers = {"User-Agent": user_agent} if user_agent else {}
    response = client.post(
        "/api/auth/login", json={"email": email, "password": TEST_PASSWORD}, headers=headers
    )
    assert response.status_code == 200, response.text


def device_events(email: str) -> list[dict]:
    return list(
        mongo_db()["security_events"].find({"actor_email": email, "type": "new_device_login"})
    )


def test_first_and_repeated_sign_ins_are_not_new(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    clear_rate_limits()
    email = new_email()
    new_user(client, email)  # the very first sign-in is never "new"
    sign_in(client, email)  # same device again

    assert device_events(email) == []


def test_sign_in_from_a_new_device_alerts_the_owner(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    clear_rate_limits()
    email = new_email()
    new_user(client, email)

    sign_in(client, email, CHROME_WINDOWS)

    found = device_events(email)
    assert len(found) == 1
    assert found[0]["details"]["device"] == "Chrome on Windows"
    assert found[0]["severity"] == "medium"

    user_id = found[0]["user_id"]
    note = mongo_db()["notifications"].find_one(
        {"user_id": user_id, "data.event_type": "new_device_login"}
    )
    assert note is not None
    assert note["title"] == "New device signed in to your account"
    assert "Chrome on Windows" in note["message"]
    assert note["link"] == "/settings?tab=devices&check=new-sign-in"

    # The sign-in itself now records which device it was.
    last = mongo_db()["activity_logs"].find_one(
        {"user_id": user_id, "action": "auth.login.success"}, sort=[("created_at", -1)]
    )
    assert last["details"]["device"] == "Chrome on Windows"


def test_a_browser_update_is_not_a_new_device(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    clear_rate_limits()
    email = new_email()
    new_user(client, email)
    sign_in(client, email, CHROME_WINDOWS)

    sign_in(client, email, CHROME_WINDOWS_UPDATED)  # same browser and system, newer version

    assert len(device_events(email)) == 1
