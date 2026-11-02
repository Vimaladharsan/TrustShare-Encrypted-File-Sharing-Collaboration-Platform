"""My Files multi-select: move, trash and download several files at once (ZIP)."""

import io
import zipfile
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.security_monitoring.detection import RULES
from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, mongo_db, new_user, upload
from tests.test_folders import create_folder, list_files


def ids(*responses) -> list[str]:
    return [r.json()["id"] for r in responses]


def test_move_selected_files_reports_the_ones_it_cannot_move(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner, other = new_user(client, new_email()), new_user(client, new_email())
    mine = ids(upload(client, owner, "a.txt", b"aaa"), upload(client, owner, "b.txt", b"bbb"))
    theirs = ids(upload(client, other, "c.txt", b"ccc"))
    folder = create_folder(client, owner, "Archive").json()

    response = client.post(
        "/api/files/bulk/move",
        json={"file_ids": mine + theirs, "folder_id": folder["id"]},
        headers=auth(owner),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == 2
    assert body["failed"] == [
        {"id": theirs[0], "type": "file", "code": "FILE_NOT_FOUND", "message": "File not found."}
    ]
    assert sorted(list_files(client, owner, folder_id=folder["id"])) == ["a.txt", "b.txt"]
    assert list_files(client, other) == ["c.txt"]  # someone else's file is untouched

    back = client.post(
        "/api/files/bulk/move", json={"file_ids": mine, "folder_id": None}, headers=auth(owner)
    )
    assert back.json()["succeeded"] == 2 and sorted(list_files(client, owner)) == ["a.txt", "b.txt"]


def test_move_to_unknown_folder_moves_nothing(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    file_ids = ids(upload(client, owner, "a.txt", b"aaa"))
    response = client.post(
        "/api/files/bulk/move",
        json={"file_ids": file_ids, "folder_id": "0123456789abcdef01234567"},
        headers=auth(owner),
    )
    assert response.status_code == 404 and list_files(client, owner) == ["a.txt"]


def test_trash_selected_files(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    a, b, c = ids(*(upload(client, owner, f"{n}.txt", n.encode() * 3) for n in "abc"))
    response = client.post("/api/files/bulk/trash", json={"file_ids": [a, b]}, headers=auth(owner))
    assert response.json() == {"succeeded": 2, "failed": []}
    assert list_files(client, owner) == ["c.txt"]
    assert sorted(list_files(client, owner, trashed=True)) == ["a.txt", "b.txt"]


def test_guest_cannot_move_or_trash(client: TestClient, new_email: Callable[[], str]) -> None:
    guest = new_user(client, new_email(), role="guest")
    selection = {"file_ids": ["0123456789abcdef01234567"]}
    assert (
        client.post("/api/files/bulk/trash", json=selection, headers=auth(guest)).status_code == 403
    )
    assert (
        client.post("/api/files/bulk/move", json=selection, headers=auth(guest)).status_code == 403
    )


def test_empty_selection_is_rejected(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    response = client.post("/api/files/bulk/download", json={"file_ids": []}, headers=auth(owner))
    assert response.status_code == 422


def test_download_selected_as_zip_with_original_bytes(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    user_id = client.get("/api/users/me", headers=auth(owner)).json()["id"]
    folder = create_folder(client, owner, "Old").json()
    selected = ids(
        upload(client, owner, "report.pdf", PDF),
        upload(client, owner, "notes.txt", b"first notes"),
        upload(client, owner, "notes.txt", b"other notes", folder_id=folder["id"]),
    )

    response = client.post(
        "/api/files/bulk/download", json={"file_ids": selected}, headers=auth(owner)
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "private, no-store"

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert archive.testzip() is None  # every entry's CRC checks out
    assert archive.namelist() == ["report.pdf", "notes.txt", "notes (2).txt"]
    assert archive.read("report.pdf") == PDF
    assert archive.read("notes.txt") == b"first notes"
    assert archive.read("notes (2).txt") == b"other notes"

    # Every file's own history gets a download; the ZIP request is recorded once on top.
    logs = mongo_db()["activity_logs"]
    per_file = list(logs.find({"user_id": user_id, "action": "file.download"}))
    assert sorted(entry["resource_id"] for entry in per_file) == sorted(selected)
    assert {entry["details"]["via"] for entry in per_file} == {"zip"}
    summary = logs.find_one({"user_id": user_id, "action": "file.download_zip"})
    assert summary["details"]["count"] == 3


def test_zip_is_refused_if_any_file_is_not_yours_or_trashed(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    owner, other = new_user(client, new_email()), new_user(client, new_email())
    mine = ids(upload(client, owner, "a.txt", b"aaa"), upload(client, owner, "b.txt", b"bbb"))
    theirs = ids(upload(client, other, "c.txt", b"ccc"))

    for selection in (mine + theirs, theirs):
        response = client.post(
            "/api/files/bulk/download", json={"file_ids": selection}, headers=auth(owner)
        )
        assert response.status_code == 404  # nothing is sent, not even a partial ZIP

    client.post(f"/api/files/{mine[1]}/trash", headers=auth(owner))
    trashed = client.post("/api/files/bulk/download", json={"file_ids": mine}, headers=auth(owner))
    assert trashed.status_code == 404

    # Admins can't download users' files either (privacy rule).
    response = client.post(
        "/api/files/bulk/download", json={"file_ids": mine[:1]}, headers=auth(admin_token)
    )
    assert response.status_code == 404


def test_zip_limits(
    client: TestClient, new_email: Callable[[], str], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = new_user(client, new_email())
    selected = ids(upload(client, owner, "a.txt", b"aaa"), upload(client, owner, "b.txt", b"bbb"))

    monkeypatch.setattr(get_settings(), "zip_max_files", 1)
    response = client.post(
        "/api/files/bulk/download", json={"file_ids": selected}, headers=auth(owner)
    )
    assert response.status_code == 400 and response.json()["error"]["code"] == "TOO_MANY_FILES"

    monkeypatch.setattr(get_settings(), "zip_max_files", 100)
    monkeypatch.setattr(get_settings(), "zip_max_mb", 0)
    response = client.post(
        "/api/files/bulk/download", json={"file_ids": selected}, headers=auth(owner)
    )
    assert response.status_code == 413 and response.json()["error"]["code"] == "ZIP_TOO_LARGE"


def test_a_zip_counts_once_for_the_excessive_downloads_rule() -> None:
    rule = next(r for r in RULES if r.name == "excessive_downloads")
    assert rule.applies({"action": "file.download", "details": {"via": "owner"}})
    assert not rule.applies({"action": "file.download", "details": {"via": "zip"}})
    assert rule.applies({"action": "file.download_zip", "details": {"count": 50}})
