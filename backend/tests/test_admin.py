"""Admin user management: change roles, disable/enable accounts, unlock lockouts."""

import asyncio
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.scripts.create_admin import make_admin
from tests.conftest import TEST_PASSWORD, file_key_row, set_last_login, stored_object
from tests.test_auth import auth, login_token, register, user_id
from tests.test_files import PDF, mongo_db, upload


@pytest.fixture
def admin_token(client: TestClient, new_email: Callable[[], str]) -> str:
    email = new_email()
    asyncio.run(make_admin(email, "Test Admin", TEST_PASSWORD))
    return login_token(client, email)


def make_user(client: TestClient, email: str) -> str:
    """Registers a normal user and returns their id."""
    response = register(client, email)
    assert response.status_code == 202, response.text
    return user_id(client, email)


def find_user(client: TestClient, token: str, email: str) -> dict:
    response = client.get("/api/admin/users", params={"search": email}, headers=auth(token))
    assert response.status_code == 200, response.text
    return next(user for user in response.json()["items"] if user["email"] == email)


# ---------- roles ----------


def test_admin_can_change_a_users_role(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    email = new_email()
    user_id = make_user(client, email)

    response = client.patch(
        f"/api/admin/users/{user_id}", json={"role": "guest"}, headers=auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["role"] == "guest"
    # The new role applies to the user's very next request (loaded fresh every time).
    me = client.get("/api/users/me", headers=auth(login_token(client, email))).json()
    assert me["role"] == "guest"
    assert "file:upload" not in me["permissions"]


def test_normal_user_cannot_change_roles(client: TestClient, new_email: Callable[[], str]) -> None:
    email, other = new_email(), new_email()
    make_user(client, email)
    other_id = make_user(client, other)

    response = client.patch(
        f"/api/admin/users/{other_id}",
        json={"role": "admin"},
        headers=auth(login_token(client, email)),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_cannot_change_own_role(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    me = client.get("/api/users/me", headers=auth(admin_token)).json()

    response = client.patch(
        f"/api/admin/users/{me['id']}", json={"role": "user"}, headers=auth(admin_token)
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CANNOT_CHANGE_SELF"


def test_invalid_role_is_rejected(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    user_id = make_user(client, new_email())

    response = client.patch(
        f"/api/admin/users/{user_id}", json={"role": "superuser"}, headers=auth(admin_token)
    )

    assert response.status_code == 422


def test_unknown_user_returns_404(client: TestClient, admin_token: str) -> None:
    response = client.patch(
        f"/api/admin/users/{uuid.uuid4()}", json={"role": "user"}, headers=auth(admin_token)
    )

    assert response.status_code == 404


# ---------- disable / enable ----------


def test_disabling_logs_the_user_out_and_blocks_login(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    email = new_email()
    user_id = make_user(client, email)
    user_token = login_token(client, email)

    response = client.patch(
        f"/api/admin/users/{user_id}", json={"is_active": False}, headers=auth(admin_token)
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Existing session stops working at once, and a new login is refused.
    assert client.get("/api/users/me", headers=auth(user_token)).status_code == 401
    login = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "ACCOUNT_DISABLED"

    # Enabling again restores access.
    client.patch(f"/api/admin/users/{user_id}", json={"is_active": True}, headers=auth(admin_token))
    assert login_token(client, email)


def test_admin_cannot_disable_themselves(client: TestClient, admin_token: str) -> None:
    me = client.get("/api/users/me", headers=auth(admin_token)).json()

    response = client.patch(
        f"/api/admin/users/{me['id']}", json={"is_active": False}, headers=auth(admin_token)
    )

    assert response.status_code == 400


# ---------- lockout ----------


def test_admin_sees_and_clears_a_lockout(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    email = new_email()
    user_id = make_user(client, email)
    for _ in range(5):
        client.post("/api/auth/login", json={"email": email, "password": "Wrong!Passw0rd"})
    assert find_user(client, admin_token, email)["is_locked"] is True

    response = client.post(f"/api/admin/users/{user_id}/unlock", headers=auth(admin_token))

    assert response.status_code == 200
    assert response.json()["is_locked"] is False
    assert login_token(client, email)  # can log in again straight away


# ---------- deleting inactive accounts ----------


def test_recently_active_account_cannot_be_deleted(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    email = new_email()
    target = make_user(client, email)
    login_token(client, email)

    response = client.delete(f"/api/admin/users/{target}", headers=auth(admin_token))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACCOUNT_STILL_ACTIVE"
    assert find_user(client, admin_token, email)["can_delete"] is False


def test_inactive_account_is_deleted_with_all_its_files(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    email = new_email()
    target = make_user(client, email)
    token = login_token(client, email)
    file_id = upload(client, token, "old.pdf", PDF).json()["id"]
    storage_key = mongo_db()["files"].find_one({"owner_id": target})["storage_key"]
    set_last_login(email, 31)
    listed = find_user(client, admin_token, email)
    assert listed["can_delete"] is True and listed["inactive_days"] == 31

    response = client.delete(f"/api/admin/users/{target}", headers=auth(admin_token))

    assert response.status_code == 204
    assert mongo_db()["files"].count_documents({"owner_id": target}) == 0
    assert stored_object(storage_key) is None  # encrypted object removed from the bucket
    assert file_key_row(file_id) is None  # and its key
    login = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login.status_code == 401
    log = mongo_db()["activity_logs"].find_one(
        {"action": "admin.user_delete", "resource_id": target}
    )
    assert log["details"]["files_deleted"] == 1


def test_admins_cannot_be_deleted(
    client: TestClient, new_email: Callable[[], str], admin_token: str
) -> None:
    email = new_email()
    asyncio.run(make_admin(email, "Other Admin", TEST_PASSWORD))
    other = user_id(client, email)  # (logs in, so set the old login time afterwards)
    set_last_login(email, 60)

    response = client.delete(f"/api/admin/users/{other}", headers=auth(admin_token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CANNOT_DELETE_ADMIN"


def test_normal_user_cannot_delete_accounts(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    target = make_user(client, email)
    set_last_login(email, 60)
    caller = new_email()
    make_user(client, caller)

    token = login_token(client, caller)

    response = client.delete(f"/api/admin/users/{target}", headers=auth(token))

    assert response.status_code == 403
