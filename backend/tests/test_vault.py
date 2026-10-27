"""Secure vault: a per-user, password-protected place for sensitive files (extra encryption)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.crypto.keyring import get_keyring
from tests.conftest import TEST_PASSWORD, file_key_row, stored_object
from tests.test_files import PDF, auth, mongo_db, new_user, upload

VAULT_PASSWORD = "Vault!Secret-2026"
SECRET_NAME = "passport scan.pdf"


def vault_headers(token: str, password: str = VAULT_PASSWORD) -> dict[str, str]:
    return {**auth(token), "X-Vault-Password": quote(password)}


def user_with_vault(client: TestClient, new_email: Callable[[], str]) -> str:
    token = new_user(client, new_email())
    created = client.post("/api/vault", json={"password": VAULT_PASSWORD}, headers=auth(token))
    assert created.status_code == 201, created.text
    return token


def vault_upload(client: TestClient, token: str, name: str = SECRET_NAME, content: bytes = PDF):
    return client.post(
        "/api/vault/files",
        files={"file": (name, content, "application/pdf")},
        headers=vault_headers(token),
    )


# ---------- setting up ----------


def test_create_vault_and_status(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    assert client.get("/api/vault", headers=auth(token)).json()["exists"] is False

    same_as_login = client.post("/api/vault", json={"password": TEST_PASSWORD}, headers=auth(token))
    created = client.post("/api/vault", json={"password": VAULT_PASSWORD}, headers=auth(token))
    again = client.post("/api/vault", json={"password": VAULT_PASSWORD}, headers=auth(token))

    assert same_as_login.status_code == 400
    assert same_as_login.json()["error"]["code"] == "VAULT_PASSWORD_REUSED"
    assert created.status_code == 201
    assert again.status_code == 409
    status = client.get("/api/vault", headers=auth(token)).json()
    assert status["exists"] is True and status["available"] is True and status["file_count"] == 0


def test_guests_have_no_vault(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email(), role="guest")

    assert client.get("/api/vault", headers=auth(token)).json()["available"] is False
    created = client.post("/api/vault", json={"password": VAULT_PASSWORD}, headers=auth(token))
    assert created.status_code == 403


# ---------- files ----------


def test_upload_list_preview_download(client: TestClient, new_email: Callable[[], str]) -> None:
    token = user_with_vault(client, new_email)

    uploaded = vault_upload(client, token)
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    listed = client.get("/api/vault/files", headers=vault_headers(token)).json()["items"]
    assert [f["name"] for f in listed] == [SECRET_NAME]
    preview = client.get(f"/api/vault/files/{file_id}/preview", headers=vault_headers(token))
    download = client.get(f"/api/vault/files/{file_id}/download", headers=vault_headers(token))
    assert preview.content == PDF and download.content == PDF
    assert "inline" in preview.headers["content-disposition"]
    assert "attachment" in download.headers["content-disposition"]
    assert client.get("/api/vault", headers=auth(token)).json()["file_count"] == 1


def test_password_is_needed_on_every_request(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = user_with_vault(client, new_email)
    file_id = vault_upload(client, token).json()["id"]

    no_header = client.get("/api/vault/files", headers=auth(token))
    wrong = client.get(
        f"/api/vault/files/{file_id}/download", headers=vault_headers(token, "not-it-123")
    )

    assert no_header.status_code == 422
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "VAULT_PASSWORD_INCORRECT"


def test_vault_files_are_double_locked_and_names_hidden(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = user_with_vault(client, new_email)
    file_id = vault_upload(client, token).json()["id"]

    doc = mongo_db()["vault_files"].find_one({"_id": ObjectId(file_id)})
    assert "original_name" not in doc and SECRET_NAME not in str(doc)  # name stored encrypted
    raw = stored_object(doc["storage_key"])
    assert raw.startswith(b"TSE1") and PDF not in raw  # ciphertext in storage

    # The server's master key alone is not enough: it only reveals the vault-sealed inner key
    # (12-byte nonce + 32-byte key + 16-byte tag), not the 32-byte file key.
    row = file_key_row(file_id)
    inner = get_keyring().unwrap(row.wrapped_key, row.key_version, file_id)
    assert len(inner) == 60


def test_vault_files_stay_out_of_my_files_and_search(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = user_with_vault(client, new_email)
    vault_upload(client, token)

    everywhere = client.get("/api/files", params={"folder_id": "all"}, headers=auth(token))
    search = client.get(
        "/api/files", params={"folder_id": "all", "q": "passport"}, headers=auth(token)
    )
    assert everywhere.json()["total"] == 0
    assert search.json()["total"] == 0


def test_rename_and_delete(client: TestClient, new_email: Callable[[], str]) -> None:
    token = user_with_vault(client, new_email)
    file_id = vault_upload(client, token).json()["id"]

    bad = client.patch(
        f"/api/vault/files/{file_id}", json={"name": "passport.exe"}, headers=vault_headers(token)
    )
    renamed = client.patch(
        f"/api/vault/files/{file_id}", json={"name": "ID card.pdf"}, headers=vault_headers(token)
    )
    assert bad.status_code == 400
    assert renamed.json()["name"] == "ID card.pdf"

    doc = mongo_db()["vault_files"].find_one({"_id": ObjectId(file_id)})
    deleted = client.delete(f"/api/vault/files/{file_id}", headers=vault_headers(token))
    assert deleted.status_code == 204
    assert stored_object(doc["storage_key"]) is None and file_key_row(file_id) is None


def test_other_users_cannot_reach_my_vault_files(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = user_with_vault(client, new_email)
    file_id = vault_upload(client, owner).json()["id"]
    other = user_with_vault(client, new_email)  # same vault password, different account

    response = client.get(f"/api/vault/files/{file_id}/download", headers=vault_headers(other))
    assert response.status_code == 404


def test_disguised_file_is_rejected(client: TestClient, new_email: Callable[[], str]) -> None:
    token = user_with_vault(client, new_email)

    response = vault_upload(client, token, "invoice.pdf", b"MZ\x90\x00 this is a program")
    assert response.status_code == 415


# ---------- moving in and out ----------


def test_move_into_vault_and_back(client: TestClient, new_email: Callable[[], str]) -> None:
    token = user_with_vault(client, new_email)
    file_id = upload(client, token, "contract.pdf", PDF).json()["id"]
    expires = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    share = client.post(
        f"/api/files/{file_id}/shares",
        json={"share_type": "link", "permission": "view", "expires_at": expires},
        headers=auth(token),
    )
    link_token = share.json()["url"].rsplit("/s/", 1)[1]

    moved_in = client.post(f"/api/vault/import/{file_id}", headers=vault_headers(token))
    assert moved_in.status_code == 200, moved_in.text
    assert client.get(f"/api/files/{file_id}", headers=auth(token)).status_code == 404
    assert client.get(f"/api/s/{link_token}").status_code == 404  # its share link is gone
    row = file_key_row(file_id)
    assert len(get_keyring().unwrap(row.wrapped_key, row.key_version, file_id)) == 60

    moved_out = client.post(f"/api/vault/files/{file_id}/move-out", headers=vault_headers(token))
    assert moved_out.status_code == 200, moved_out.text
    assert moved_out.json()["name"] == "contract.pdf"
    download = client.get(f"/api/files/{file_id}/download", headers=auth(token))
    assert download.content == PDF  # same encrypted object, only the key was re-locked


# ---------- password rules ----------


def test_wrong_passwords_lock_the_vault(client: TestClient, new_email: Callable[[], str]) -> None:
    token = user_with_vault(client, new_email)

    for _ in range(get_settings().max_failed_logins):
        client.get("/api/vault/files", headers=vault_headers(token, "guess-guess"))
    locked = client.get("/api/vault/files", headers=vault_headers(token))

    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "VAULT_LOCKED"
    assert client.get("/api/vault", headers=auth(token)).json()["locked_minutes"] > 0
    event = mongo_db()["security_events"].find_one({"type": "vault_locked"}, sort=[("_id", -1)])
    assert event is not None and event["severity"] == "high"


def test_change_vault_password(client: TestClient, new_email: Callable[[], str]) -> None:
    token = user_with_vault(client, new_email)
    file_id = vault_upload(client, token).json()["id"]
    new_password = "Brand-New-Väult-9"  # non-ASCII works (header is URL-encoded)

    changed = client.post(
        "/api/vault/password",
        json={"current_password": VAULT_PASSWORD, "new_password": new_password},
        headers=auth(token),
    )
    assert changed.status_code == 204, changed.text

    old = client.get("/api/vault/files", headers=vault_headers(token))
    new = client.get("/api/vault/files", headers=vault_headers(token, new_password))
    assert old.status_code == 403
    assert [f["name"] for f in new.json()["items"]] == [SECRET_NAME]
    download = client.get(
        f"/api/vault/files/{file_id}/download", headers=vault_headers(token, new_password)
    )
    assert download.content == PDF


def test_reset_forgotten_vault_deletes_everything(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = user_with_vault(client, new_email)
    file_id = vault_upload(client, token).json()["id"]
    doc = mongo_db()["vault_files"].find_one({"_id": ObjectId(file_id)})

    wrong = client.post(
        "/api/vault/reset",
        json={"account_password": "nope", "confirm": "DELETE"},
        headers=auth(token),
    )
    reset = client.post(
        "/api/vault/reset",
        json={"account_password": TEST_PASSWORD, "confirm": "DELETE"},
        headers=auth(token),
    )

    assert wrong.status_code == 400
    assert reset.json() == {"files_deleted": 1}
    assert stored_object(doc["storage_key"]) is None and file_key_row(file_id) is None
    assert client.get("/api/vault", headers=auth(token)).json()["exists"] is False


def test_vault_counts_toward_storage_and_logs_no_names(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = user_with_vault(client, new_email)
    vault_upload(client, token)

    usage = client.get("/api/files/usage", headers=auth(token)).json()
    assert usage["used_bytes"] == len(PDF)
    me = client.get("/api/users/me", headers=auth(token)).json()
    logs = list(mongo_db()["activity_logs"].find({"user_id": me["id"], "resource_type": "vault"}))
    assert {log["action"] for log in logs} >= {"vault.created", "vault.file_added"}
    assert "passport" not in str(logs)


def test_deleting_the_account_erases_the_vault(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = user_with_vault(client, new_email)
    file_id = vault_upload(client, token).json()["id"]
    doc = mongo_db()["vault_files"].find_one({"_id": ObjectId(file_id)})

    deleted = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": TEST_PASSWORD, "confirm": "DELETE"},
        headers=auth(token),
    )

    assert deleted.status_code == 204, deleted.text
    assert stored_object(doc["storage_key"]) is None
    assert mongo_db()["vault_files"].find_one({"_id": doc["_id"]}) is None
