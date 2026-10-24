"""My account: profile name, signed-in devices, deleting the account, new backup codes."""

from collections.abc import Callable

from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.user_agent import describe_device
from tests.conftest import TEST_PASSWORD, file_key_row, stored_object
from tests.test_files import PDF, mongo_db, upload
from tests.test_mfa import auth, enable_mfa, next_code, register_and_login

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)


def login(client: TestClient, email: str, user_agent: str = "testclient") -> str:
    client.cookies.clear()
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
        headers={"User-Agent": user_agent},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


# ---------- profile ----------


def test_update_my_name(client: TestClient, new_email: Callable[[], str]) -> None:
    token = register_and_login(client, new_email())

    response = client.patch(
        "/api/users/me", json={"full_name": "  Asha   Raman "}, headers=auth(token)
    )
    too_short = client.patch("/api/users/me", json={"full_name": " A "}, headers=auth(token))

    assert response.status_code == 200 and response.json()["full_name"] == "Asha Raman"
    assert client.get("/api/users/me", headers=auth(token)).json()["full_name"] == "Asha Raman"
    assert too_short.status_code == 422


# ---------- devices ----------


def test_devices_list_shows_each_signed_in_device(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register_and_login(client, email)
    laptop = login(client, email, CHROME_WINDOWS)
    login(client, email, SAFARI_IPHONE)

    items = client.get("/api/users/me/sessions", headers=auth(laptop)).json()["items"]

    described = {(d["browser"], d["os"], d["kind"]) for d in items}
    assert ("Chrome", "Windows", "desktop") in described
    assert ("Safari", "iOS", "mobile") in described
    current = [d for d in items if d["current"]]
    assert len(current) == 1 and current[0]["browser"] == "Chrome"


def test_signing_out_a_device_stops_it_immediately(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    register_and_login(client, email)
    laptop = login(client, email, CHROME_WINDOWS)
    phone = login(client, email, SAFARI_IPHONE)
    phone_refresh = client.cookies.get("refresh_token")
    phone_id = next(
        d["id"]
        for d in client.get("/api/users/me/sessions", headers=auth(laptop)).json()["items"]
        if d["os"] == "iOS"
    )

    response = client.delete(f"/api/users/me/sessions/{phone_id}", headers=auth(laptop))

    assert response.status_code == 204
    assert client.get("/api/users/me", headers=auth(phone)).status_code == 401  # access token
    client.cookies.clear()
    refreshed = client.post(
        "/api/auth/refresh",
        headers={"Cookie": f"refresh_token={phone_refresh}", "User-Agent": SAFARI_IPHONE},
    )
    assert refreshed.status_code == 401  # and its refresh token
    assert client.get("/api/users/me", headers=auth(laptop)).status_code == 200  # others stay


def test_cannot_sign_out_someone_elses_device(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = register_and_login(client, new_email())
    owner_device = client.get("/api/users/me/sessions", headers=auth(owner)).json()["items"][0]
    stranger = register_and_login(client, new_email())

    response = client.delete(f"/api/users/me/sessions/{owner_device['id']}", headers=auth(stranger))

    assert response.status_code == 404
    assert client.get("/api/users/me", headers=auth(owner)).status_code == 200


def test_device_names_from_user_agents() -> None:
    assert describe_device(CHROME_WINDOWS) == {
        "browser": "Chrome",
        "os": "Windows",
        "kind": "desktop",
    }
    assert describe_device(SAFARI_IPHONE)["os"] == "iOS"
    edge = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/141.0 Safari/537.36 Edg/141.0"
    assert describe_device(edge)["browser"] == "Edge"
    assert describe_device("")["browser"] == "Unknown browser"


# ---------- delete my account ----------


def test_delete_account_needs_password_and_typed_confirmation(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = register_and_login(client, new_email())

    no_confirm = client.request(
        "DELETE", "/api/users/me", json={"password": TEST_PASSWORD, "confirm": "yes"},
        headers=auth(token),
    )  # fmt: skip
    wrong_password = client.request(
        "DELETE", "/api/users/me", json={"password": "Wrong!Pass123", "confirm": "DELETE"},
        headers=auth(token),
    )  # fmt: skip

    assert no_confirm.json()["error"]["code"] == "CONFIRMATION_MISMATCH"
    assert wrong_password.json()["error"]["code"] == "WRONG_PASSWORD"
    assert client.get("/api/users/me", headers=auth(token)).status_code == 200  # still there


def test_delete_account_erases_everything(
    client: TestClient, new_email: Callable[[], str], outbox
) -> None:
    email = new_email()
    token = register_and_login(client, email)
    owner_id = client.get("/api/users/me", headers=auth(token)).json()["id"]
    file_id = upload(client, token, "report.pdf", PDF).json()["id"]
    key = mongo_db()["files"].find_one({"_id": ObjectId(file_id)})["storage_key"]

    response = client.request(
        "DELETE", "/api/users/me", json={"password": TEST_PASSWORD, "confirm": "DELETE"},
        headers=auth(token),
    )  # fmt: skip

    assert response.status_code == 204
    assert client.get("/api/users/me", headers=auth(token)).status_code == 401
    login_again = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login_again.status_code == 401
    assert mongo_db()["files"].count_documents({"owner_id": owner_id}) == 0
    assert stored_object(key) is None and file_key_row(file_id) is None
    assert any(m.to == email and "deleted" in m.subject for m in outbox.sent)
    assert mongo_db()["activity_logs"].find_one({"action": "account.deleted", "user_id": owner_id})


def test_delete_account_with_two_step_needs_a_code(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = register_and_login(client, new_email())
    phone, _ = enable_mfa(client, token)
    body = {"password": TEST_PASSWORD, "confirm": "DELETE"}

    without_code = client.request("DELETE", "/api/users/me", json=body, headers=auth(token))
    with_code = client.request(
        "DELETE", "/api/users/me", json={**body, "code": next_code(phone)}, headers=auth(token)
    )

    assert without_code.json()["error"]["code"] == "INVALID_MFA_CODE"
    assert with_code.status_code == 204


# ---------- backup codes ----------


def test_regenerating_backup_codes_replaces_the_old_ones(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email = new_email()
    token = register_and_login(client, email)
    phone, old_codes = enable_mfa(client, token)

    wrong = client.post(
        "/api/users/me/mfa/backup-codes", json={"code": "000000"}, headers=auth(token)
    )
    response = client.post(
        "/api/users/me/mfa/backup-codes", json={"code": next_code(phone)}, headers=auth(token)
    )

    assert wrong.status_code == 400
    new_codes = response.json()["backup_codes"]
    assert response.status_code == 200 and len(new_codes) == 10
    assert not set(new_codes) & set(old_codes)
    status = client.get("/api/users/me/mfa", headers=auth(token)).json()
    assert status["backup_codes_remaining"] == 10
    challenge = client.post(
        "/api/auth/login", json={"email": email, "password": TEST_PASSWORD}
    ).json()["challenge_id"]
    old = client.post(
        "/api/auth/mfa/verify", json={"challenge_id": challenge, "code": old_codes[0]}
    )
    new = client.post(
        "/api/auth/mfa/verify", json={"challenge_id": challenge, "code": new_codes[0]}
    )
    assert old.status_code == 401 and new.status_code == 200
