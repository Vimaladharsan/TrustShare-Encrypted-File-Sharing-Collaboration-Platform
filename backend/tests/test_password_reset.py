"""Forgot password → emailed link → new password."""

import re
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.email_service import Email, get_email_sender
from tests.conftest import TEST_PASSWORD
from tests.test_auth import auth, login_token, register

NEW_PASSWORD = "N3w!Passw0rd-Reset"


class FakeSender:
    """Collects emails instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


@pytest.fixture
def outbox() -> Iterator[FakeSender]:
    sender = FakeSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    yield sender
    app.dependency_overrides.pop(get_email_sender, None)


def ask_for_reset(client: TestClient, email: str):
    return client.post("/api/auth/forgot-password", json={"email": email})


def token_from(email: Email) -> str:
    match = re.search(r"reset-password\?token=([\w-]+)", email.text)
    assert match, email.text
    return match.group(1)


def reset(client: TestClient, token: str, password: str = NEW_PASSWORD):
    return client.post("/api/auth/reset-password", json={"token": token, "new_password": password})


def test_reset_link_is_emailed(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()
    register(client, email)

    response = ask_for_reset(client, email)

    assert response.status_code == 202
    assert len(outbox.sent) == 1
    assert outbox.sent[0].to == email
    assert "/reset-password?token=" in outbox.sent[0].text


def test_unknown_email_gets_the_same_answer_and_no_email(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    known = new_email()
    register(client, known)

    for_known = ask_for_reset(client, known)
    for_unknown = ask_for_reset(client, new_email())

    assert for_unknown.status_code == for_known.status_code == 202
    assert for_unknown.json() == for_known.json()  # nothing reveals which emails exist
    assert len(outbox.sent) == 1


def test_reset_changes_password_and_logs_out_everywhere(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()
    register(client, email)
    old_session = login_token(client, email)
    ask_for_reset(client, email)

    response = reset(client, token_from(outbox.sent[0]))

    assert response.status_code == 200
    assert client.get("/api/users/me", headers=auth(old_session)).status_code == 401
    old = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert old.status_code == 401
    assert login_token(client, email, NEW_PASSWORD)  # a login right after the reset works


def test_reset_link_works_only_once(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()
    register(client, email)
    ask_for_reset(client, email)
    token = token_from(outbox.sent[0])

    assert reset(client, token).status_code == 200
    second = reset(client, token, "An0ther!Passw0rd")

    assert second.status_code == 400
    assert second.json()["error"]["code"] == "INVALID_RESET_LINK"


def test_weak_password_is_rejected_without_using_up_the_link(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()
    register(client, email)
    ask_for_reset(client, email)
    token = token_from(outbox.sent[0])

    weak = reset(client, token, "alllowercase1!")

    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"
    assert reset(client, token).status_code == 200  # the same link still works


def test_asking_again_cancels_the_previous_link(
    client: TestClient, new_email: Callable[[], str], outbox: FakeSender
) -> None:
    email = new_email()
    register(client, email)
    ask_for_reset(client, email)
    ask_for_reset(client, email)
    first, latest = token_from(outbox.sent[0]), token_from(outbox.sent[1])

    assert reset(client, first).status_code == 400
    assert reset(client, latest).status_code == 200


def test_made_up_token_is_rejected(client: TestClient) -> None:
    response = reset(client, "x" * 43)

    assert response.status_code == 400
