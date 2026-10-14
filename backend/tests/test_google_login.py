"""Google login: state/PKCE redirect, account create/link, MFA step, error redirects.
Google itself is replaced by a fake client, so the tests never contact Google."""

import asyncio
import uuid
from collections.abc import Callable, Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.main import app
from app.models import User
from app.services.google_oauth_service import GoogleIdentity, get_google_client
from tests.test_auth import register


class FakeGoogle:
    """Pretends Google signed in whoever `identity` says."""

    def __init__(self) -> None:
        self.identity: GoogleIdentity | None = None

    async def identify(self, code: str, code_verifier: str) -> GoogleIdentity:
        assert code == "code-from-google" and code_verifier
        assert self.identity is not None
        return self.identity


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGoogle]:
    settings = get_settings()
    # Test values (restored afterwards, so a real .env configuration isn't touched).
    monkeypatch.setattr(settings, "google_client_id", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_client_secret", SecretStr("test-secret"))
    fake = FakeGoogle()
    app.dependency_overrides[get_google_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_google_client, None)


def start(client: TestClient) -> str:
    """Begins the login and returns the `state` we sent to Google."""
    response = client.get("/api/auth/google/login", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["state"][0]


def callback(client: TestClient, state: str, **params: str):
    return client.get(
        "/api/auth/google/callback",
        params={"code": "code-from-google", "state": state, **params},
        follow_redirects=False,
    )


def frontend(response) -> tuple[str, dict[str, list[str]]]:
    location = urlparse(response.headers["location"])
    return location.path, parse_qs(location.query)


def sign_in(client: TestClient, google: FakeGoogle, email: str, sub: str | None = None):
    google.identity = GoogleIdentity(sub=sub or uuid.uuid4().hex, email=email, name="Google User")
    return callback(client, start(client))


def set_mfa(email: str) -> None:
    async def run() -> None:
        engine = create_async_engine(get_settings().postgres_url)
        async with engine.begin() as conn:
            await conn.execute(update(User).where(User.email == email).values(mfa_enabled=True))
        await engine.dispose()

    asyncio.run(run())


def test_login_redirects_to_google_with_state_and_pkce(client: TestClient, google: FakeGoogle):
    response = client.get("/api/auth/google/login", follow_redirects=False)

    location = urlparse(response.headers["location"])
    query = parse_qs(location.query)
    assert location.netloc == "accounts.google.com"
    assert query["client_id"] == [get_settings().google_client_id]
    assert query["state"][0] and query["code_challenge_method"] == ["S256"]
    assert "openid" in query["scope"][0]


def test_first_google_login_creates_a_verified_user(
    client: TestClient, new_email: Callable[[], str], google: FakeGoogle
) -> None:
    email = new_email()

    response = sign_in(client, google, email)

    assert frontend(response)[0] == "/auth/google"
    assert "refresh_token" in response.cookies
    session = client.post("/api/auth/refresh").json()  # what the frontend does next
    assert session["user"]["email"] == email
    assert session["user"]["role"] == "user"
    assert session["user"]["is_email_verified"] is True


def test_existing_account_with_same_email_is_linked(
    client: TestClient, new_email: Callable[[], str], google: FakeGoogle
) -> None:
    email = new_email()
    user_id = register(client, email).json()["id"]
    sub = uuid.uuid4().hex

    sign_in(client, google, email, sub)
    first = client.post("/api/auth/refresh").json()["user"]
    client.cookies.clear()
    # Next time Google is found by its own id, even if the Gmail address changed.
    sign_in(client, google, new_email(), sub)
    second = client.post("/api/auth/refresh").json()["user"]

    assert first["id"] == second["id"] == user_id


def test_state_must_match(client: TestClient, google: FakeGoogle) -> None:
    google.identity = GoogleIdentity(sub="x", email="x@example.com", name="X")

    response = callback(client, "made-up-state")

    path, query = frontend(response)
    assert path == "/login"
    assert "expired" in query["oauth_error"][0]


def test_state_works_only_once(
    client: TestClient, new_email: Callable[[], str], google: FakeGoogle
) -> None:
    google.identity = GoogleIdentity(sub=uuid.uuid4().hex, email=new_email(), name="X")
    state = start(client)

    assert frontend(callback(client, state))[0] == "/auth/google"
    assert frontend(callback(client, state))[0] == "/login"


def test_cancel_on_google_returns_to_login(client: TestClient, google: FakeGoogle) -> None:
    response = client.get(
        "/api/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False
    )

    assert frontend(response)[1]["oauth_error"] == ["Google sign-in was cancelled."]


def test_mfa_users_still_need_their_code(
    client: TestClient, new_email: Callable[[], str], google: FakeGoogle
) -> None:
    email = new_email()
    register(client, email)
    set_mfa(email)

    response = sign_in(client, google, email)

    path, query = frontend(response)
    assert path == "/login"
    assert query["mfa_challenge"][0]
    assert "refresh_token" not in response.cookies  # no session before the second factor


def test_button_hidden_and_login_refused_when_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    assert client.get("/api/auth/providers").json() == {"google": False}

    response = client.get("/api/auth/google/login", follow_redirects=False)

    assert frontend(response)[0] == "/login"
    assert "not set up" in frontend(response)[1]["oauth_error"][0]
