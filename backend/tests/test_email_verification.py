"""Email verification: link emailed on sign-up, single use, resend, optional strict mode."""

import re
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.email_service import Email
from tests.conftest import TEST_PASSWORD, FakeSender
from tests.test_auth import auth, login_token, register


def token_from(email: Email) -> str:
    match = re.search(r"verify-email\?token=([\w-]+)", email.text)
    assert match, email.text
    return match.group(1)


def verify(client: TestClient, token: str):
    return client.post("/api/auth/verify-email", json={"token": token})


def me(client: TestClient, email: str) -> dict:
    return client.get("/api/users/me", headers=auth(login_token(client, email))).json()


@pytest.fixture
def strict_mode() -> Iterator[None]:
    settings = get_settings()
    settings.require_email_verification = True
    yield
    settings.require_email_verification = False


def test_sign_up_sends_a_verification_link(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()

    response = register(client, email)

    assert response.status_code == 201
    assert response.json()["is_email_verified"] is False
    emails = outbox.links("verify-email")
    assert len(emails) == 1
    assert emails[0].to == email


def test_link_verifies_the_email(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()
    register(client, email)

    response = verify(client, token_from(outbox.links("verify-email")[0]))

    assert response.status_code == 200
    assert me(client, email)["is_email_verified"] is True


def test_verification_link_works_only_once(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    register(client, new_email())
    token = token_from(outbox.links("verify-email")[0])

    assert verify(client, token).status_code == 200
    second = verify(client, token)

    assert second.status_code == 400
    assert second.json()["error"]["code"] == "INVALID_VERIFY_LINK"


def test_resend_sends_a_new_link_and_cancels_the_old_one(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()
    register(client, email)
    token = login_token(client, email)

    response = client.post("/api/auth/verify-email/resend", headers=auth(token))

    assert response.status_code == 202
    first, latest = (token_from(e) for e in outbox.links("verify-email"))
    assert verify(client, first).status_code == 400
    assert verify(client, latest).status_code == 200
    # Once verified, there's nothing to resend.
    again = client.post("/api/auth/verify-email/resend", headers=auth(token))
    assert again.json()["error"]["code"] == "ALREADY_VERIFIED"


def test_soft_mode_lets_unverified_users_log_in(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register(client, email)

    assert login_token(client, email)  # default: a reminder in the UI, not a block


def test_strict_mode_blocks_login_until_verified(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender, strict_mode: None
) -> None:
    email = new_email()
    register(client, email)
    credentials = {"email": email, "password": TEST_PASSWORD}

    blocked = client.post("/api/auth/login", json=credentials)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    verify(client, token_from(outbox.links("verify-email")[0]))
    assert client.post("/api/auth/login", json=credentials).status_code == 200
