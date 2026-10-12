"""Folders, rename/move, trash/restore and delete forever (Phase 4B – demo item 4)."""

from collections.abc import Callable
from pathlib import Path

from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.test_files import PDF, auth, mongo_db, new_user, upload


def create_folder(client: TestClient, token: str, name: str, parent_id: str | None = None):
    return client.post(
        "/api/folders", headers=auth(token), json={"name": name, "parent_id": parent_id}
    )


def list_files(client: TestClient, token: str, **params) -> list[str]:
    response = client.get("/api/files", headers=auth(token), params=params)
    return [f["name"] for f in response.json()["items"]]


def list_folders(client: TestClient, token: str, **params) -> list[str]:
    response = client.get("/api/folders", headers=auth(token), params=params)
    return [f["name"] for f in response.json()["items"]]


# ---------- creating and browsing ----------


def test_nested_folders_and_breadcrumbs(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    finance = create_folder(client, token, "Finance").json()
    tax = create_folder(client, token, "Tax 2026", finance["id"]).json()
    q1 = create_folder(client, token, "Q1", tax["id"]).json()

    detail = client.get(f"/api/folders/{q1['id']}", headers=auth(token)).json()

    assert [c["name"] for c in detail["breadcrumbs"]] == ["Finance", "Tax 2026", "Q1"]
    assert list_folders(client, token) == ["Finance"]
    assert list_folders(client, token, parent_id=finance["id"]) == ["Tax 2026"]


def test_duplicate_folder_name_in_same_place_is_rejected(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    create_folder(client, token, "Reports")

    response = create_folder(client, token, "reports")  # same name, different case

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FOLDER_EXISTS"


def test_invalid_folder_name_is_rejected(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())

    response = create_folder(client, token, "../etc")

    assert response.status_code == 400


def test_upload_into_folder_and_list_by_folder(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    folder = create_folder(client, token, "Invoices").json()
    upload(client, token, "top.pdf", PDF)
    upload(client, token, "inside.pdf", PDF, folder_id=folder["id"], allow_duplicate="true")

    assert list_files(client, token) == ["top.pdf"]  # top level only
    assert list_files(client, token, folder_id=folder["id"]) == ["inside.pdf"]
    assert sorted(list_files(client, token, folder_id="all")) == ["inside.pdf", "top.pdf"]


# ---------- rename and move ----------


def test_rename_and_move_file(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    folder = create_folder(client, token, "Archive").json()
    file_id = upload(client, token, "draft.pdf", PDF).json()["id"]

    renamed = client.patch(f"/api/files/{file_id}", headers=auth(token), json={"name": "final.pdf"})
    moved = client.patch(
        f"/api/files/{file_id}", headers=auth(token), json={"folder_id": folder["id"]}
    )
    back = client.patch(f"/api/files/{file_id}", headers=auth(token), json={"folder_id": None})

    assert renamed.json()["name"] == "final.pdf"
    assert moved.json()["folder_id"] == folder["id"]
    assert back.json()["folder_id"] is None


def test_rename_cannot_change_extension(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "report.pdf", PDF).json()["id"]

    response = client.patch(f"/api/files/{file_id}", headers=auth(token), json={"name": "x.exe"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EXTENSION_CHANGE_NOT_ALLOWED"


def test_moving_folder_updates_breadcrumbs_of_subfolders(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    a = create_folder(client, token, "A").json()
    b = create_folder(client, token, "B", a["id"]).json()
    c = create_folder(client, token, "C", b["id"]).json()
    other = create_folder(client, token, "Other").json()

    client.patch(f"/api/folders/{b['id']}", headers=auth(token), json={"parent_id": other["id"]})

    crumbs = client.get(f"/api/folders/{c['id']}", headers=auth(token)).json()["breadcrumbs"]
    assert [x["name"] for x in crumbs] == ["Other", "B", "C"]


def test_folder_cannot_move_into_its_own_subfolder(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    parent = create_folder(client, token, "Parent").json()
    child = create_folder(client, token, "Child", parent["id"]).json()

    response = client.patch(
        f"/api/folders/{parent['id']}", headers=auth(token), json={"parent_id": child["id"]}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MOVE"


# ---------- trash, restore, delete ----------


def test_trash_and_restore_file(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "oops.pdf", PDF).json()["id"]

    assert client.post(f"/api/files/{file_id}/trash", headers=auth(token)).status_code == 204
    assert list_files(client, token) == []
    assert list_files(client, token, trashed="true") == ["oops.pdf"]

    restored = client.post(f"/api/files/{file_id}/restore", headers=auth(token))
    assert restored.json()["status"] == "active"
    assert list_files(client, token) == ["oops.pdf"]


def test_trashing_folder_trashes_contents_and_restore_brings_them_back(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    folder = create_folder(client, token, "Project").json()
    sub = create_folder(client, token, "Drafts", folder["id"]).json()
    upload(client, token, "plan.pdf", PDF, folder_id=sub["id"])

    client.post(f"/api/folders/{folder['id']}/trash", headers=auth(token))

    assert list_folders(client, token) == []
    assert list_folders(client, token, trashed="true") == ["Project"]
    assert list_files(client, token, folder_id="all") == []

    client.post(f"/api/folders/{folder['id']}/restore", headers=auth(token))

    assert list_folders(client, token, parent_id=folder["id"]) == ["Drafts"]
    assert list_files(client, token, folder_id=sub["id"]) == ["plan.pdf"]


def test_delete_forever_removes_bytes_and_metadata(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "gone.pdf", PDF).json()["id"]
    storage_key = mongo_db()["files"].find_one({"_id": ObjectId(file_id)})["storage_key"]

    response = client.delete(f"/api/files/{file_id}", headers=auth(token))

    assert response.status_code == 204
    assert client.get(f"/api/files/{file_id}", headers=auth(token)).status_code == 404
    assert not (Path(get_settings().storage_dir) / storage_key).exists()
    assert client.get("/api/files/usage", headers=auth(token)).json()["used_bytes"] == 0


# ---------- who may do what ----------


def test_guest_cannot_create_folders(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email(), role="guest")

    assert create_folder(client, token, "Nope").status_code == 403


def test_other_users_folders_are_invisible(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    stranger = new_user(client, new_email())
    folder = create_folder(client, owner, "Private").json()

    assert client.get(f"/api/folders/{folder['id']}", headers=auth(stranger)).status_code == 404
    # ...and nobody can upload into someone else's folder.
    response = upload(client, stranger, "sneaky.pdf", PDF, folder_id=folder["id"])
    assert response.status_code == 404
