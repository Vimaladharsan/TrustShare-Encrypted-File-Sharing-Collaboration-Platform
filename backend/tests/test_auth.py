import asyncio
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.scripts.create_admin import make_admin
from tests.conftest import TEST_PASSWORD


def register(client: TestClient, email: str, password: str = TEST_PASSWORD):
    return client.post(
        "/api/auth/register",
        json={"full_name": "Test User", "email": email, "password": password},
    )


def login_token(client: TestClient, email: str, password: str = TEST_PASSWORD) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------- registration ----------


def test_register_creates_user_with_user_role(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    response = register(client, email)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["role"] == "user"
    assert "file:upload" in body["permissions"]
    assert "password" not in str(body).lower()  # no password or hash ever leaves the API


def test_register_rejects_weak_password(client: TestClient, new_email: Callable[[], str]) -> None:
    response = register(client, new_email(), password="password123")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_rejects_duplicate_email_case_insensitively(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)

    response = register(client, email.upper())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


# ---------- login ----------


def test_login_returns_jwt_and_user(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    register(client, email)

    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2  # header.payload.signature
    assert body["expires_in"] == 15 * 60
    assert body["user"]["email"] == email


def test_login_wrong_password_and_unknown_email_look_identical(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)

    wrong_password = client.post("/api/auth/login", json={"email": email, "password": "Wr0ng!pass"})
    unknown_email = client.post(
        "/api/auth/login", json={"email": new_email(), "password": TEST_PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["error"]["code"] == unknown_email.json()["error"]["code"]


# ---------- protected routes ----------


def test_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_rejects_a_tampered_token(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    register(client, email)
    token = login_token(client, email)
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")

    response = client.get("/api/users/me", headers=auth(tampered))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_me_returns_the_logged_in_user(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    register(client, email)

    response = client.get("/api/users/me", headers=auth(login_token(client, email)))

    assert response.status_code == 200
    assert response.json()["email"] == email


# ---------- role-based access (demo item 2) ----------


def test_normal_user_is_forbidden_from_admin_route(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)

    response = client.get("/api/admin/users", headers=auth(login_token(client, email)))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_list_users(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    asyncio.run(make_admin(email, "Test Admin", TEST_PASSWORD))

    response = client.get("/api/admin/users", headers=auth(login_token(client, email)))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(user["email"] == email for user in body["items"]) or body["total"] > 20
