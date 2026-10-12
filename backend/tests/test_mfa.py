"""Two-step verification with TOTP and backup codes (Phase 3C).

pyotp plays the role of the phone's authenticator app.
"""

import time
from collections.abc import Callable

import pyotp
from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client: TestClient, email: str) -> str:
    client.post(
        "/api/auth/register",
        json={"full_name": "MFA User", "email": email, "password": TEST_PASSWORD},
    )
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    return response.json()["access_token"]


def enable_mfa(client: TestClient, token: str) -> tuple[pyotp.TOTP, list[str]]:
    """Runs setup + enable like a user scanning the QR code. Returns (phone app, backup codes)."""
    setup = client.post("/api/users/me/mfa/setup", headers=auth(token))
    assert setup.status_code == 200, setup.text
    phone = pyotp.TOTP(setup.json()["secret"])
    enable = client.post(
        "/api/users/me/mfa/enable", headers=auth(token), json={"code": phone.now()}
    )
    assert enable.status_code == 200, enable.text
    return phone, enable.json()["backup_codes"]


def next_code(phone: pyotp.TOTP) -> str:
    # The code for the next 30 s window: accepted (clock-drift allowance) and not used yet.
    return phone.at(time.time() + 30)


def start_login(client: TestClient, email: str) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return response.json()


# ---------- setup ----------


def test_setup_returns_qr_code_and_secret(client: TestClient, new_email: Callable[[], str]) -> None:
    token = register_and_login(client, new_email())

    response = client.post("/api/users/me/mfa/setup", headers=auth(token))

    body = response.json()
    assert response.status_code == 200
    assert body["qr_code"].startswith("data:image/svg+xml;base64,")
    assert body["otpauth_uri"].startswith("otpauth://totp/TrustShare:")
    assert len(body["secret"]) == 32


def test_enable_rejects_a_wrong_code(client: TestClient, new_email: Callable[[], str]) -> None:
    token = register_and_login(client, new_email())
    client.post("/api/users/me/mfa/setup", headers=auth(token))

    response = client.post("/api/users/me/mfa/enable", headers=auth(token), json={"code": "000000"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MFA_CODE"


def test_enable_turns_mfa_on_and_returns_ten_backup_codes(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = register_and_login(client, new_email())

    _, backup_codes = enable_mfa(client, token)

    assert len(backup_codes) == 10
    assert len(set(backup_codes)) == 10
    status = client.get("/api/users/me/mfa", headers=auth(token)).json()
    assert status == {"enabled": True, "backup_codes_remaining": 10}


# ---------- login with MFA ----------


def test_login_with_mfa_needs_a_code_before_tokens(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    phone, _ = enable_mfa(client, register_and_login(client, email))
    client.cookies.clear()

    step_1 = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})

    assert step_1.json()["mfa_required"] is True
    assert "access_token" not in step_1.json()
    assert "refresh_token" not in step_1.cookies  # no session before the second factor

    step_2 = client.post(
        "/api/auth/mfa/verify",
        json={"challenge_id": step_1.json()["challenge_id"], "code": next_code(phone)},
    )

    assert step_2.status_code == 200
    assert step_2.json()["access_token"]
    assert "refresh_token" in step_2.cookies


def test_wrong_mfa_code_is_rejected(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    enable_mfa(client, register_and_login(client, email))
    challenge = start_login(client, email)["challenge_id"]

    response = client.post(
        "/api/auth/mfa/verify", json={"challenge_id": challenge, "code": "000000"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_MFA_CODE"


def test_the_same_code_cannot_be_used_twice(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    phone, _ = enable_mfa(client, register_and_login(client, email))
    code = next_code(phone)

    first = client.post(
        "/api/auth/mfa/verify",
        json={"challenge_id": start_login(client, email)["challenge_id"], "code": code},
    )
    replay = client.post(
        "/api/auth/mfa/verify",
        json={"challenge_id": start_login(client, email)["challenge_id"], "code": code},
    )

    assert first.status_code == 200
    assert replay.status_code == 401


def test_backup_code_works_exactly_once(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    _, backup_codes = enable_mfa(client, register_and_login(client, email))

    first = client.post(
        "/api/auth/mfa/verify",
        json={"challenge_id": start_login(client, email)["challenge_id"], "code": backup_codes[0]},
    )
    again = client.post(
        "/api/auth/mfa/verify",
        json={"challenge_id": start_login(client, email)["challenge_id"], "code": backup_codes[0]},
    )

    assert first.status_code == 200
    assert again.status_code == 401
    status = client.get("/api/users/me/mfa", headers=auth(first.json()["access_token"])).json()
    assert status["backup_codes_remaining"] == 9


def test_challenge_id_must_be_valid(client: TestClient) -> None:
    response = client.post(
        "/api/auth/mfa/verify", json={"challenge_id": "not-a-real-challenge", "code": "123456"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MFA_CHALLENGE_EXPIRED"


# ---------- turning MFA off ----------


def test_disable_needs_password_and_code(client: TestClient, new_email: Callable[[], str]) -> None:
    token = register_and_login(client, new_email())
    phone, _ = enable_mfa(client, token)

    wrong_password = client.post(
        "/api/users/me/mfa/disable",
        headers=auth(token),
        json={"password": "Wr0ng!Password", "code": next_code(phone)},
    )
    ok = client.post(
        "/api/users/me/mfa/disable",
        headers=auth(token),
        json={"password": TEST_PASSWORD, "code": next_code(phone)},
    )

    assert wrong_password.status_code == 401
    assert ok.status_code == 204
    assert client.get("/api/users/me/mfa", headers=auth(token)).json()["enabled"] is False
