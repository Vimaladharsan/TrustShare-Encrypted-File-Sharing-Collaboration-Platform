"""Delete folders forever, bulk restore/delete, restore all and empty trash."""

from collections.abc import Callable
from pathlib import Path

from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.test_files import PDF, auth, mongo_db, new_user, upload
from tests.test_folders import create_folder, list_files, list_folders


def storage_path(file_id: str) -> Path:
    doc = mongo_db()["files"].find_one({"_id": ObjectId(file_id)})
    return Path(get_settings().storage_dir) / doc["storage_key"]


def usage(client: TestClient, token: str) -> int:
    return client.get("/api/files/usage", headers=auth(token)).json()["used_bytes"]


def trash_file(client: TestClient, token: str, file_id: str) -> None:
    client.post(f"/api/files/{file_id}/trash", headers=auth(token))


def trash_folder(client: TestClient, token: str, folder_id: str) -> None:
    client.post(f"/api/folders/{folder_id}/trash", headers=auth(token))


# ---------- delete a folder forever ----------


def test_deleting_folder_forever_removes_everything_inside(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    top = create_folder(client, token, "Project").json()
    sub = create_folder(client, token, "Drafts", top["id"]).json()
    file_a = upload(client, token, "a.pdf", PDF, folder_id=top["id"]).json()["id"]
    file_b = upload(client, token, "b.txt", b"notes", folder_id=sub["id"]).json()["id"]
    disk = [storage_path(file_a), storage_path(file_b)]
    trash_folder(client, token, top["id"])

    response = client.delete(f"/api/folders/{top['id']}", headers=auth(token))

    assert response.status_code == 204
    assert all(not path.exists() for path in disk)  # bytes gone
    assert (
        mongo_db()["files"].count_documents({"_id": {"$in": [ObjectId(file_a), ObjectId(file_b)]}})
        == 0
    )  # metadata gone
    assert (
        mongo_db()["folders"].count_documents(
            {"_id": {"$in": [ObjectId(top["id"]), ObjectId(sub["id"])]}}
        )
        == 0
    )
    assert usage(client, token) == 0
    assert list_folders(client, token, trashed="true") == []


def test_folder_must_be_in_trash_before_deleting_forever(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    folder = create_folder(client, token, "Keep").json()

    response = client.delete(f"/api/folders/{folder['id']}", headers=auth(token))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "NOT_IN_TRASH"


# ---------- bulk actions ----------


def test_restore_selected_restores_only_those(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    keep = upload(client, token, "keep.pdf", PDF).json()["id"]
    back = upload(client, token, "back.txt", b"come back").json()["id"]
    trash_file(client, token, keep)
    trash_file(client, token, back)

    response = client.post(
        "/api/trash/restore", headers=auth(token), json={"file_ids": [back], "folder_ids": []}
    )

    assert response.json() == {"succeeded": 1, "failed": []}
    assert list_files(client, token) == ["back.txt"]
    assert list_files(client, token, trashed="true") == ["keep.pdf"]


def test_delete_selected_reports_items_it_cannot_delete(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    stranger = new_user(client, new_email())
    mine = upload(client, owner, "mine.pdf", PDF).json()["id"]
    theirs = upload(client, stranger, "theirs.pdf", PDF).json()["id"]
    trash_file(client, owner, mine)
    trash_file(client, stranger, theirs)

    response = client.post(
        "/api/trash/delete", headers=auth(owner), json={"file_ids": [mine, theirs]}
    )

    body = response.json()
    assert body["succeeded"] == 1
    assert [f["id"] for f in body["failed"]] == [theirs]  # someone else's file is untouched
    assert client.get(f"/api/files/{theirs}", headers=auth(stranger)).status_code == 200


def test_restore_all_brings_back_files_and_folders(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    folder = create_folder(client, token, "Old").json()
    upload(client, token, "inside.pdf", PDF, folder_id=folder["id"])
    loose = upload(client, token, "loose.txt", b"loose").json()["id"]
    trash_folder(client, token, folder["id"])
    trash_file(client, token, loose)

    response = client.post("/api/trash/restore-all", headers=auth(token))

    assert response.json()["succeeded"] == 2
    assert list_folders(client, token) == ["Old"]
    assert list_files(client, token) == ["loose.txt"]
    assert list_files(client, token, folder_id=folder["id"]) == ["inside.pdf"]


def test_empty_trash_deletes_only_trashed_items(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    outer = create_folder(client, token, "Outer").json()
    inner = create_folder(client, token, "Inner", outer["id"]).json()
    upload(client, token, "deep.pdf", PDF, folder_id=inner["id"])
    trash_folder(client, token, inner["id"])  # trashed on its own first...
    trash_folder(client, token, outer["id"])  # ...then its parent too
    gone = upload(client, token, "gone.txt", b"bye").json()["id"]
    trash_file(client, token, gone)
    upload(client, token, "stays.txt", b"still here")

    response = client.post("/api/trash/empty", headers=auth(token))

    assert response.json()["failed"] == []
    assert list_files(client, token, trashed="true") == []
    assert list_folders(client, token, trashed="true") == []
    assert list_files(client, token, folder_id="all") == ["stays.txt"]
    assert usage(client, token) == len(b"still here")


def test_guest_cannot_empty_trash(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email(), role="guest")

    response = client.post("/api/trash/empty", headers=auth(token))

    assert response.status_code == 403
