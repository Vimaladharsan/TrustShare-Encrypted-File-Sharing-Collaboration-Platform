"""Refresh tokens, logout, lockout and rate limiting (Phase 3B)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import TEST_PASSWORD, clear_rate_limits


def register_and_login(client: TestClient, email: str) -> tuple[str, str]:
    """Returns (access token, refresh token) for a new user."""
    client.post(
        "/api/auth/register",
        json={"full_name": "Session User", "email": email, "password": TEST_PASSWORD},
    )
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"], response.cookies["refresh_token"]


def refresh_with(client: TestClient, refresh_token: str, user_agent: str = "testclient"):
    client.cookies.clear()
    return client.post(
        "/api/auth/refresh",
        headers={"Cookie": f"refresh_token={refresh_token}", "User-Agent": user_agent},
    )


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------- refresh tokens ----------


def test_login_sets_secure_refresh_cookie(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    client.post(
        "/api/auth/register",
        json={"full_name": "Cookie User", "email": email, "password": TEST_PASSWORD},
    )
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})

    cookie_header = response.headers["set-cookie"].lower()
    assert "refresh_token=" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    assert "path=/api/auth" in cookie_header


def test_refresh_returns_new_access_token_and_rotates_cookie(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, refresh_token = register_and_login(client, new_email())

    response = refresh_with(client, refresh_token)

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.cookies["refresh_token"] != refresh_token  # rotated


def test_reusing_an_old_refresh_token_revokes_every_session(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, first = register_and_login(client, new_email())
    second = refresh_with(client, first).cookies["refresh_token"]

    reuse = refresh_with(client, first, user_agent="attacker-browser")  # a stolen copy

    assert reuse.status_code == 401
    # Theft detected: even the legitimate newer token no longer works.
    assert refresh_with(client, second).status_code == 401


def test_same_browser_may_retry_a_just_rotated_token(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    """Two tabs or a fast reload send the old cookie once more: no logout for that."""
    _, first = register_and_login(client, new_email())
    second = refresh_with(client, first).cookies["refresh_token"]

    retry = refresh_with(client, first)  # same IP and browser, within the grace window

    assert retry.status_code == 200
    assert retry.cookies["refresh_token"] not in (first, second)
    assert refresh_with(client, second).status_code == 200  # nobody was logged out


def test_reuse_after_the_grace_window_is_theft(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    settings = get_settings()
    settings.refresh_reuse_grace_seconds = 0  # as if the window had already passed
    try:
        _, first = register_and_login(client, new_email())
        second = refresh_with(client, first).cookies["refresh_token"]
        reuse = refresh_with(client, first)
    finally:
        settings.refresh_reuse_grace_seconds = 10

    assert reuse.status_code == 401
    assert refresh_with(client, second).status_code == 401


def test_refresh_without_cookie_is_rejected(client: TestClient) -> None:
    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SESSION"


# ---------- logout ----------


def test_logout_ends_the_session_and_blocks_the_access_token(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    access, refresh_token = register_and_login(client, new_email())
    client.cookies.clear()

    response = client.post(
        "/api/auth/logout",
        headers={**auth(access), "Cookie": f"refresh_token={refresh_token}"},
    )

    assert response.status_code == 204
    assert refresh_with(client, refresh_token).status_code == 401
    assert client.get("/api/users/me", headers=auth(access)).status_code == 401


def test_logout_all_ends_every_session(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    access_1, refresh_1 = register_and_login(client, email)
    login_2 = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    refresh_2 = login_2.cookies["refresh_token"]

    response = client.post("/api/auth/logout-all", headers=auth(access_1))

    assert response.status_code == 204
    assert refresh_with(client, refresh_1).status_code == 401
    assert refresh_with(client, refresh_2).status_code == 401
    assert client.get("/api/users/me", headers=auth(access_1)).status_code == 401


# ---------- brute-force protection ----------


def test_account_locks_after_too_many_wrong_passwords(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register_and_login(client, email)
    wrong = {"email": email, "password": "Wr0ng!Password"}

    for _ in range(get_settings().max_failed_logins):
        assert client.post("/api/auth/login", json=wrong).status_code == 401

    # Even the correct password is refused while locked.
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert int(response.headers["Retry-After"]) > 0


def test_login_is_rate_limited_per_ip(
    client: TestClient, new_email: Callable[[], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_rate_limits()
    monkeypatch.setattr(get_settings(), "login_rate_limit_per_minute", 3)
    attempt = {"email": new_email(), "password": "Wr0ng!Password"}

    codes = [client.post("/api/auth/login", json=attempt).status_code for _ in range(4)]

    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429
    clear_rate_limits()
