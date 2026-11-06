"""Optional passwords on share links, and sharing a whole folder."""

from collections.abc import Callable
from urllib.parse import quote

from fastapi.testclient import TestClient

from tests.conftest import share_row
from tests.test_files import PDF, auth, new_user, upload
from tests.test_folders import create_folder
from tests.test_shares import in_days, link_token, owner_with_file, share


def pw(password: str) -> dict[str, str]:
    return {"X-Share-Password": quote(password)}


# ---------- password-protected links ----------


def test_link_with_password(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id, permission="download", password="open sesame ü")
    token, share_id = link_token(created), created.json()["id"]
    assert created.json()["has_password"] is True
    assert share_row(share_id).password_hash.startswith("$2")  # bcrypt, never the password

    for path in ("", "/preview", "/download"):
        missing = client.get(f"/api/s/{token}{path}")
        assert missing.status_code == 403
        assert missing.json()["error"]["code"] == "SHARE_PASSWORD_REQUIRED"
        assert "report.pdf" not in missing.text  # nothing about the file before the password

    wrong = client.get(f"/api/s/{token}", headers=pw("guess"))
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "SHARE_PASSWORD_INVALID"

    ok = client.get(f"/api/s/{token}", headers=pw("open sesame ü"))
    assert ok.status_code == 200 and ok.json()["file_name"] == "report.pdf"
    assert client.get(f"/api/s/{token}/download", headers=pw("open sesame ü")).content == PDF

    history = client.get(f"/api/shares/{share_id}/access", headers=auth(owner)).json()["items"]
    assert any(item["detail"] == "wrong password" for item in history)


def test_five_wrong_passwords_lock_the_visitor_out(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    token = link_token(share(client, owner, file_id, password="right-one"))

    for _ in range(5):
        assert client.get(f"/api/s/{token}", headers=pw("nope")).status_code == 403
    locked = client.get(f"/api/s/{token}", headers=pw("right-one"))  # even the right one now
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "SHARE_PASSWORD_LOCKED"


def test_links_without_password_still_work(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id)
    assert created.json()["has_password"] is False
    assert client.get(f"/api/s/{link_token(created)}").status_code == 200


def test_password_can_be_added_and_removed_later(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id)
    token, share_id = link_token(created), created.json()["id"]

    added = client.patch(
        f"/api/shares/{share_id}", json={"password": "later-pw"}, headers=auth(owner)
    )
    assert added.json()["has_password"] is True
    assert client.get(f"/api/s/{token}").status_code == 403
    assert client.get(f"/api/s/{token}", headers=pw("later-pw")).status_code == 200

    removed = client.patch(f"/api/shares/{share_id}", json={"password": None}, headers=auth(owner))
    assert removed.json()["has_password"] is False
    assert client.get(f"/api/s/{token}").status_code == 200


def test_password_rules(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    new_user(client, recipient_email)

    assert share(client, owner, file_id, password="abc").status_code == 422  # too short
    direct = share(
        client, owner, file_id, share_type="user", recipient_email=recipient_email, password="abcd"
    )
    assert direct.status_code == 422  # passwords are for links only


# ---------- share a whole folder ----------


def test_share_a_folder_with_a_person(
    client: TestClient, new_email: Callable[[], str], outbox
) -> None:
    owner = new_user(client, new_email())
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    work = create_folder(client, owner, "Work").json()
    sub = create_folder(client, owner, "Drafts", work["id"]).json()
    upload(client, owner, "plan.pdf", PDF, folder_id=work["id"])
    upload(client, owner, "notes.txt", b"draft notes", folder_id=sub["id"])
    upload(client, owner, "outside.txt", b"not in the folder")
    outbox.sent.clear()

    response = client.post(
        f"/api/folders/{work['id']}/shares",
        json={"share_type": "user", "recipient_email": recipient_email, "permission": "download"},
        headers=auth(owner),
    )

    assert response.status_code == 201
    assert sorted(s["file_name"] for s in response.json()["created"]) == ["notes.txt", "plan.pdf"]
    received = client.get("/api/shares/received", headers=auth(recipient)).json()["items"]
    assert sorted(s["file_name"] for s in received) == ["notes.txt", "plan.pdf"]
    notices = [
        n
        for n in client.get("/api/notifications", headers=auth(recipient)).json()["items"]
        if n["type"] == "file_shared"
    ]
    assert len(notices) == 1 and notices[0]["title"] == "A folder was shared with you"
    assert "“Work” (2 files)" in notices[0]["message"]
    emails = [m for m in outbox.sent if m.to == recipient_email]
    assert len(emails) == 1 and '"Work"' in emails[0].subject


def test_share_a_folder_by_links_with_a_password(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    folder = create_folder(client, owner, "Photos").json()
    upload(client, owner, "a.txt", b"aaa", folder_id=folder["id"])
    upload(client, owner, "b.txt", b"bbb", folder_id=folder["id"])

    response = client.post(
        f"/api/folders/{folder['id']}/shares",
        json={
            "share_type": "link",
            "permission": "view",
            "expires_at": in_days(3),
            "password": "pics",
        },
        headers=auth(owner),
    )

    created = response.json()["created"]
    assert len(created) == 2 and all(s["has_password"] for s in created)
    token = created[0]["url"].rsplit("/s/", 1)[1]
    assert client.get(f"/api/s/{token}").status_code == 403
    assert client.get(f"/api/s/{token}", headers=pw("pics")).status_code == 200


def test_folder_share_rules(client: TestClient, new_email: Callable[[], str]) -> None:
    owner, stranger = new_user(client, new_email()), new_user(client, new_email())
    empty = create_folder(client, owner, "Empty").json()
    body = {"share_type": "link", "permission": "view", "expires_at": in_days(3)}

    response = client.post(f"/api/folders/{empty['id']}/shares", json=body, headers=auth(owner))
    assert response.status_code == 400 and response.json()["error"]["code"] == "FOLDER_EMPTY"
    response = client.post(f"/api/folders/{empty['id']}/shares", json=body, headers=auth(stranger))
    assert response.status_code == 404  # not their folder
