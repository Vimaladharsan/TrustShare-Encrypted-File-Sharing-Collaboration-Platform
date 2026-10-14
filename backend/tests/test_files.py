"""File upload, validation, storage and access rules (Phase 4A – demo item 3)."""

import hashlib
import io
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.config import get_settings
from tests.conftest import TEST_PASSWORD, set_role

PDF = b"%PDF-1.4\n% TrustShare test file\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"


def make_docx(with_word_part: bool = True) -> bytes:
    """A minimal ZIP shaped like a Word file (or a fake one missing the Word part)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        if with_word_part:
            archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def new_user(client: TestClient, email: str, role: str = "user") -> str:
    """Register (and optionally change role); returns an access token."""
    client.post(
        "/api/auth/register",
        json={"full_name": "File User", "email": email, "password": TEST_PASSWORD},
    )
    if role != "user":
        set_role(email, role)
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    return response.json()["access_token"]


def upload(client: TestClient, token: str, name: str, content: bytes, **params):
    return client.post(
        "/api/files",
        headers=auth(token),
        params=params,
        files={"file": (name, content, "application/octet-stream")},
    )


def mongo_db():
    settings = get_settings()
    return MongoClient(settings.mongo_url)[settings.mongo_db]


# ---------- successful upload ----------


def test_upload_pdf_saves_file_and_metadata(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())

    response = upload(client, token, "Q3 Report.pdf", PDF)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Q3 Report.pdf"
    assert body["category"] == "document"
    assert body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert body["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert "storage_key" not in body  # where it's stored is never revealed

    # The metadata document exists in MongoDB...
    doc = mongo_db()["files"].find_one({"_id": ObjectId(body["id"])})
    assert doc["original_name"] == "Q3 Report.pdf"
    assert doc["status"] == "active"
    # ...and the bytes are on disk under a random name, not the user's filename.
    stored = Path(get_settings().storage_dir) / doc["storage_key"]
    assert stored.read_bytes() == PDF
    assert "Q3 Report" not in str(stored)


def test_download_returns_the_same_bytes_as_attachment(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "notes.pdf", PDF).json()["id"]

    response = client.get(f"/api/files/{file_id}/download", headers=auth(token))

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-disposition"].startswith('attachment; filename="notes.pdf"')
    assert response.headers["x-content-type-options"] == "nosniff"


def test_preview_shows_pdf_inline_in_a_sandbox(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "notes.pdf", PDF).json()["id"]

    response = client.get(f"/api/files/{file_id}/preview", headers=auth(token))

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith('inline; filename="notes.pdf"')
    assert response.headers["content-security-policy"].startswith("sandbox")


def test_preview_sends_text_as_plain_text(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    # Even if a .txt file contains HTML, it must never be shown as a web page.
    file_id = upload(client, token, "page.txt", b"<script>alert(1)</script>").json()["id"]

    response = client.get(f"/api/files/{file_id}/preview", headers=auth(token))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


def test_preview_not_offered_for_office_files(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "letter.docx", make_docx()).json()["id"]

    response = client.get(f"/api/files/{file_id}/preview", headers=auth(token))

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "PREVIEW_NOT_SUPPORTED"


def test_preview_of_another_users_file_is_not_found(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    file_id = upload(client, owner, "private.pdf", PDF).json()["id"]
    stranger = new_user(client, new_email())

    response = client.get(f"/api/files/{file_id}/preview", headers=auth(stranger))

    assert response.status_code == 404


def test_upload_valid_word_document(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())

    response = upload(client, token, "letter.docx", make_docx())

    assert response.status_code == 201
    assert response.json()["category"] == "document"


def test_upload_is_logged_in_activity_log(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "log-me.pdf", PDF).json()["id"]

    entry = mongo_db()["activity_logs"].find_one({"action": "file.upload", "resource_id": file_id})

    assert entry is not None
    assert entry["status"] == "success"
    assert entry["details"]["file_name"] == "log-me.pdf"


# ---------- rejected uploads ----------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("setup.exe", b"MZ\x90\x00\x03"),  # forbidden extension
        ("report.pdf", b"MZ\x90\x00\x03 not really a pdf"),  # renamed .exe
        ("fake.docx", make_docx(with_word_part=False)),  # a ZIP that isn't a Word file
        ("binary.txt", b"hello\x00world"),  # "text" with binary content
        ("noextension", b"just some text"),
    ],
)
def test_disallowed_or_mismatched_files_are_rejected(
    client: TestClient, new_email: Callable[[], str], name: str, content: bytes
) -> None:
    token = new_user(client, new_email())

    response = upload(client, token, name, content)

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_rejected_upload_is_logged(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    token = new_user(client, email)
    upload(client, token, "virus.pdf", b"MZ\x90\x00")

    entry = mongo_db()["activity_logs"].find_one(
        {"actor_email": email, "action": "file.upload_rejected"}
    )

    assert entry["status"] == "failure"
    assert entry["details"]["reason"] == "UNSUPPORTED_FILE_TYPE"


def test_file_over_size_limit_is_rejected(
    client: TestClient, new_email: Callable[[], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    token = new_user(client, new_email())
    big_pdf = PDF + b"0" * (1024 * 1024 + 10)  # just over 1 MB

    response = upload(client, token, "big.pdf", big_pdf)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_beyond_quota_is_rejected(
    client: TestClient, new_email: Callable[[], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "default_quota_mb", 1)  # new accounts get 1 MB
    token = new_user(client, new_email())

    response = upload(client, token, "big.pdf", PDF + b"0" * (1024 * 1024 + 10))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_empty_file_is_rejected(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())

    response = upload(client, token, "empty.txt", b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_FILE"


def test_duplicate_is_detected_unless_allowed(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    upload(client, token, "a.pdf", PDF)

    duplicate = upload(client, token, "copy-of-a.pdf", PDF)
    keep_both = upload(client, token, "copy-of-a.pdf", PDF, allow_duplicate="true")

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_FILE"
    assert keep_both.status_code == 201


# ---------- who may do what ----------


def test_guest_cannot_upload(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email(), role="guest")

    response = upload(client, token, "a.pdf", PDF)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_other_users_files_are_invisible(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    stranger = new_user(client, new_email())
    file_id = upload(client, owner, "private.pdf", PDF).json()["id"]

    assert client.get(f"/api/files/{file_id}", headers=auth(stranger)).status_code == 404
    download = client.get(f"/api/files/{file_id}/download", headers=auth(stranger))
    assert download.status_code == 404
    listing = client.get("/api/files", headers=auth(stranger)).json()
    assert all(item["id"] != file_id for item in listing["items"])


def test_admin_can_view_any_users_file(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    admin = new_user(client, new_email(), role="admin")
    file_id = upload(client, owner, "audit-me.pdf", PDF).json()["id"]

    response = client.get(f"/api/files/{file_id}", headers=auth(admin))

    assert response.status_code == 200


def test_invalid_file_id_returns_404(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())

    assert client.get("/api/files/not-an-id", headers=auth(token)).status_code == 404


# ---------- listing ----------


def test_list_search_filter_and_usage(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    upload(client, token, "Budget 2026.pdf", PDF)
    upload(client, token, "notes.txt", b"meeting notes")

    everything = client.get("/api/files", headers=auth(token)).json()
    search = client.get("/api/files", headers=auth(token), params={"q": "budget"}).json()
    texts = client.get("/api/files", headers=auth(token), params={"category": "text"}).json()
    usage = client.get("/api/files/usage", headers=auth(token)).json()

    assert everything["total"] == 2
    assert [f["name"] for f in search["items"]] == ["Budget 2026.pdf"]
    assert [f["name"] for f in texts["items"]] == ["notes.txt"]
    assert usage["used_bytes"] == len(PDF) + len(b"meeting notes")
    assert usage["quota_bytes"] == get_settings().default_quota_mb * 1024 * 1024
