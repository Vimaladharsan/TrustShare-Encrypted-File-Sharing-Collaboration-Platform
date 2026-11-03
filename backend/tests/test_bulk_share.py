"""Sharing several files at once: one link per file, or one person gets all – told only once."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.test_admin import admin_token  # noqa: F401 – fixture
from tests.test_files import PDF, auth, make_docx, mongo_db, new_user, upload
from tests.test_shares import in_days


def bulk(client: TestClient, token: str, file_ids: list[str], **body):
    body.setdefault("share_type", "link")
    if body["share_type"] == "link":
        body.setdefault("expires_at", in_days(7))
    return client.post("/api/shares/bulk", json={"file_ids": file_ids, **body}, headers=auth(token))


def three_files(client: TestClient, token: str) -> list[str]:
    return [
        upload(client, token, name, content).json()["id"]
        for name, content in (("a.pdf", PDF), ("b.txt", b"bee"), ("c.txt", b"sea"))
    ]


def test_one_link_per_file(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    file_ids = three_files(client, owner)

    response = bulk(client, owner, file_ids, permission="view")

    assert response.status_code == 201
    created = response.json()["created"]
    assert [share["file_id"] for share in created] == file_ids
    assert response.json()["failed"] == []
    tokens = {share["url"].rsplit("/s/", 1)[1] for share in created}
    assert len(tokens) == 3  # three different secret links
    for token in tokens:
        assert client.get(f"/api/s/{token}").status_code == 200


def test_person_gets_all_files_but_one_notice_and_one_email(
    client: TestClient, new_email: Callable[[], str], outbox
) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    file_ids = three_files(client, owner)
    outbox.sent.clear()

    response = bulk(
        client,
        owner,
        file_ids,
        share_type="user",
        recipient_email=recipient_email,
        permission="download",
    )

    assert response.status_code == 201 and len(response.json()["created"]) == 3
    received = client.get("/api/shares/received", headers=auth(recipient)).json()["items"]
    assert sorted(share["file_name"] for share in received) == ["a.pdf", "b.txt", "c.txt"]

    notices = client.get("/api/notifications", headers=auth(recipient)).json()["items"]
    shared = [n for n in notices if n["type"] == "file_shared"]
    assert len(shared) == 1
    assert shared[0]["title"] == "3 files were shared with you"
    emails = [m for m in outbox.sent if m.to == recipient_email]
    assert len(emails) == 1 and "3 files" in emails[0].subject


def test_each_file_is_checked_on_its_own(client: TestClient, new_email: Callable[[], str]) -> None:
    owner, stranger = new_user(client, new_email()), new_user(client, new_email())
    mine = upload(client, owner, "ok.pdf", PDF).json()["id"]
    word = upload(client, owner, "plan.docx", make_docx()).json()["id"]
    theirs = upload(client, stranger, "x.pdf", PDF).json()["id"]

    response = bulk(client, owner, [mine, word, theirs], permission="view")

    body = response.json()
    assert [share["file_id"] for share in body["created"]] == [mine]
    assert {(f["file_id"], f["code"]) for f in body["failed"]} == {
        (word, "VIEW_NOT_SUPPORTED"),  # Word files can't be view-only
        (theirs, "FILE_NOT_FOUND"),  # not mine
    }


def test_unknown_person_stops_everything(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    file_ids = three_files(client, owner)

    response = bulk(client, owner, file_ids, share_type="user", recipient_email=new_email())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECIPIENT_NOT_FOUND"
    assert client.get("/api/shares/sent", headers=auth(owner)).json()["items"] == []


def test_validation_and_permissions(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    guest = new_user(client, new_email(), role="guest")
    file_id = upload(client, owner, "a.pdf", PDF).json()["id"]

    assert bulk(client, owner, []).status_code == 422
    assert bulk(client, owner, [file_id], share_type="user").status_code == 422  # no email
    assert bulk(client, guest, [file_id]).status_code == 403


def test_admin_sees_the_batch_without_file_names(
    client: TestClient,
    new_email: Callable[[], str],
    admin_token: str,  # noqa: F811
) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    new_user(client, recipient_email)
    owner_id = client.get("/api/users/me", headers=auth(owner)).json()["id"]
    bulk(
        client,
        owner,
        three_files(client, owner),
        share_type="user",
        recipient_email=recipient_email,
    )

    batch = mongo_db()["activity_logs"].find_one(
        {"user_id": owner_id, "action": "share.create_batch"}
    )
    assert batch["details"]["count"] == 3

    audit = client.get(f"/api/audit-logs/user/{owner_id}", headers=auth(admin_token))
    assert "Shared 3 files with one person" in audit.text
    for name in ("a.pdf", "b.txt", "c.txt"):
        assert name not in audit.text
    feed = client.get(
        "/api/activity-monitoring/activities",
        params={"user_id": owner_id},
        headers=auth(admin_token),
    )
    assert "a.pdf" not in feed.text
