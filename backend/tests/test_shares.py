"""Sharing (Milestone 2, Phase 5): secret links and direct shares, with every access rule."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.middleware import safe_path
from tests.conftest import set_role, share_row, update_share
from tests.test_files import PDF, auth, make_docx, mongo_db, new_user, upload


def in_days(days: float) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def share(client: TestClient, token: str, file_id: str, **body):
    body.setdefault("share_type", "link")
    if body["share_type"] == "link":
        body.setdefault("expires_at", in_days(7))
    return client.post(f"/api/files/{file_id}/shares", json=body, headers=auth(token))


def link_token(response) -> str:
    assert response.status_code == 201, response.text
    return response.json()["url"].rsplit("/s/", 1)[1]


def owner_with_file(client: TestClient, new_email: Callable[[], str]) -> tuple[str, str, str]:
    email = new_email()
    token = new_user(client, email)
    file_id = upload(client, token, "report.pdf", PDF).json()["id"]
    return email, token, file_id


# ---------- share links ----------


def test_link_lets_anyone_view_and_download(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id, permission="download")
    token = link_token(created)

    info = client.get(f"/api/s/{token}")  # no login
    preview = client.get(f"/api/s/{token}/preview")
    download = client.get(f"/api/s/{token}/download")

    assert info.status_code == 200
    assert info.json()["file_name"] == "report.pdf" and info.json()["permission"] == "download"
    assert preview.status_code == 200 and preview.content == PDF
    assert download.status_code == 200 and download.content == PDF
    assert "attachment" in download.headers["content-disposition"]


def test_only_the_hash_of_the_link_is_stored(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id)
    token = link_token(created)

    row = share_row(created.json()["id"])
    listing = client.get("/api/shares/sent", headers=auth(owner)).json()

    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.token_hash
    assert token not in str(listing) and row.token_hash not in str(listing)
    assert "url" not in listing["items"][0]  # the link is shown only once, at creation


def test_view_only_link_cannot_download(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    token = link_token(share(client, owner, file_id, permission="view"))

    assert client.get(f"/api/s/{token}/preview").status_code == 200
    response = client.get(f"/api/s/{token}/download")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SHARE_DOWNLOAD_NOT_ALLOWED"
    assert PDF not in response.content


def test_view_link_needs_a_previewable_file(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    file_id = upload(client, owner, "notes.docx", make_docx()).json()["id"]

    response = share(client, owner, file_id, permission="view")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VIEW_NOT_SUPPORTED"


def test_link_expiry_rules(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)

    missing = client.post(
        f"/api/files/{file_id}/shares", json={"share_type": "link"}, headers=auth(owner)
    )
    past = share(client, owner, file_id, expires_at=in_days(-1))
    too_far = share(client, owner, file_id, expires_at=in_days(31))

    for response in (missing, past, too_far):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_EXPIRY"


def test_expired_link_stops_working(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id, permission="download")
    token = link_token(created)
    update_share(created.json()["id"], expires_at=datetime.now(UTC) - timedelta(minutes=1))

    for path in ("", "/preview", "/download"):
        response = client.get(f"/api/s/{token}{path}")
        assert response.status_code == 410
        assert response.json()["error"]["code"] == "SHARE_EXPIRED"
    status = client.get(f"/api/files/{file_id}/shares", headers=auth(owner)).json()
    assert status["items"][0]["status"] == "expired"


def test_revoked_link_stops_working(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id)
    token = link_token(created)

    revoke = client.delete(f"/api/shares/{created.json()['id']}", headers=auth(owner))
    response = client.get(f"/api/s/{token}")

    assert revoke.status_code == 204
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "SHARE_REVOKED"


def test_only_the_owner_can_revoke(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id)
    stranger = new_user(client, new_email())

    response = client.delete(f"/api/shares/{created.json()['id']}", headers=auth(stranger))

    assert response.status_code == 404
    assert client.get(f"/api/s/{link_token(created)}").status_code == 200


def test_download_limit(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    token = link_token(share(client, owner, file_id, permission="download", max_downloads=2))

    assert client.get(f"/api/s/{token}").json()["downloads_left"] == 2
    first = client.get(f"/api/s/{token}/download")
    second = client.get(f"/api/s/{token}/download")
    third = client.get(f"/api/s/{token}/download")

    assert first.status_code == 200 and second.status_code == 200
    assert third.status_code == 410
    assert third.json()["error"]["code"] == "SHARE_LIMIT_REACHED"


def test_download_limit_needs_download_permission(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)

    response = share(client, owner, file_id, permission="view", max_downloads=3)

    assert response.status_code == 422


def test_trashed_file_link_stops_and_restore_brings_it_back(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    token = link_token(share(client, owner, file_id))

    client.post(f"/api/files/{file_id}/trash", headers=auth(owner))
    while_trashed = client.get(f"/api/s/{token}")
    client.post(f"/api/files/{file_id}/restore", headers=auth(owner))
    after_restore = client.get(f"/api/s/{token}")

    assert while_trashed.status_code == 404
    assert after_restore.status_code == 200


def test_deleting_the_file_removes_its_shares(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id)

    client.delete(f"/api/files/{file_id}", headers=auth(owner))

    assert share_row(created.json()["id"]) is None
    assert client.get(f"/api/s/{link_token(created)}").status_code == 404


def test_owner_losing_share_permission_disables_links(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    email, owner, file_id = owner_with_file(client, new_email)
    token = link_token(share(client, owner, file_id))

    set_role(email, "guest")  # guests may not share
    response = client.get(f"/api/s/{token}")

    assert response.status_code == 404


def test_unknown_and_malformed_links(client: TestClient) -> None:
    unknown = client.get(f"/api/s/{'A' * 43}")
    malformed = client.get("/api/s/short")

    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "SHARE_NOT_FOUND"
    assert malformed.status_code == 422


def test_link_downloads_are_logged_without_the_token(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    token = link_token(share(client, owner, file_id, permission="download"))

    client.get(f"/api/s/{token}/download")

    log = mongo_db()["activity_logs"].find_one(
        {"action": "file.download", "resource_id": file_id, "details.via": "link"}
    )
    assert log is not None and log["user_id"] is None
    assert token not in str(log)
    assert safe_path(f"/api/s/{token}/download") == "/api/s/***/download"


# ---------- direct shares with registered people ----------


def test_direct_share_appears_in_shared_with_me(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)

    created = share(
        client, owner, file_id, share_type="user", recipient_email=recipient_email,
        permission="download",
    )  # fmt: skip
    received = client.get("/api/shares/received", headers=auth(recipient)).json()["items"]
    share_id = received[0]["id"]
    download = client.get(f"/api/shares/{share_id}/download", headers=auth(recipient))

    assert created.status_code == 201 and created.json()["url"] is None
    assert created.json()["recipient_email"] == recipient_email
    assert received[0]["file_name"] == "report.pdf"
    assert download.status_code == 200 and download.content == PDF


def test_others_cannot_use_a_direct_share(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    new_user(client, recipient_email)
    share_id = share(
        client, owner, file_id, share_type="user", recipient_email=recipient_email
    ).json()["id"]
    stranger = new_user(client, new_email())
    admin = new_user(client, new_email(), role="admin")

    for token in (stranger, admin):  # admins get no special access either
        response = client.get(f"/api/shares/{share_id}/preview", headers=auth(token))
        assert response.status_code == 404


def test_view_only_direct_share_cannot_download(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    share_id = share(
        client, owner, file_id, share_type="user", recipient_email=recipient_email
    ).json()["id"]

    preview = client.get(f"/api/shares/{share_id}/preview", headers=auth(recipient))
    download = client.get(f"/api/shares/{share_id}/download", headers=auth(recipient))

    assert preview.status_code == 200 and preview.content == PDF
    assert download.status_code == 403


def test_direct_share_validation(client: TestClient, new_email: Callable[[], str]) -> None:
    owner_email, owner, file_id = owner_with_file(client, new_email)
    friend = new_email()
    new_user(client, friend)

    yourself = share(client, owner, file_id, share_type="user", recipient_email=owner_email)
    nobody = share(client, owner, file_id, share_type="user", recipient_email=new_email())
    first = share(client, owner, file_id, share_type="user", recipient_email=friend)
    again = share(client, owner, file_id, share_type="user", recipient_email=friend)

    assert yourself.json()["error"]["code"] == "CANNOT_SHARE_WITH_SELF"
    assert nobody.status_code == 404
    assert first.status_code == 201
    assert again.status_code == 409


def test_revoked_direct_share_disappears(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    share_id = share(
        client, owner, file_id, share_type="user", recipient_email=recipient_email
    ).json()["id"]

    client.delete(f"/api/shares/{share_id}", headers=auth(owner))

    assert client.get("/api/shares/received", headers=auth(recipient)).json()["items"] == []
    response = client.get(f"/api/shares/{share_id}/preview", headers=auth(recipient))
    assert response.status_code == 410


def test_guest_can_receive_but_not_share(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    guest_email = new_email()
    guest = new_user(client, guest_email, role="guest")
    share_id = share(client, owner, file_id, share_type="user", recipient_email=guest_email).json()[
        "id"
    ]

    preview = client.get(f"/api/shares/{share_id}/preview", headers=auth(guest))
    reshare = share(client, guest, file_id)

    assert preview.status_code == 200
    assert reshare.status_code == 403


def test_cannot_share_someone_elses_file(client: TestClient, new_email: Callable[[], str]) -> None:
    _, _, file_id = owner_with_file(client, new_email)
    stranger = new_user(client, new_email())

    response = share(client, stranger, file_id)

    assert response.status_code == 404


def test_shared_by_me_lists_status(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    active = share(client, owner, file_id).json()
    revoked = share(client, owner, file_id).json()
    client.delete(f"/api/shares/{revoked['id']}", headers=auth(owner))

    items = {
        item["id"]: item
        for item in client.get("/api/shares/sent", headers=auth(owner)).json()["items"]
    }

    assert items[active["id"]]["status"] == "active"
    assert items[revoked["id"]]["status"] == "revoked"
    assert items[active["id"]]["file_name"] == "report.pdf"


def test_recipient_is_emailed_about_a_direct_share(
    client: TestClient, new_email: Callable[[], str], outbox
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    new_user(client, recipient_email)

    share(client, owner, file_id, share_type="user", recipient_email=recipient_email,
          permission="download", expires_at=in_days(3))  # fmt: skip
    share(client, owner, file_id)  # a link share: nobody to email

    mails = [m for m in outbox.sent if m.to == recipient_email and "shared" in m.subject]
    assert len(mails) == 1
    assert '"report.pdf"' in mails[0].subject
    assert "/shared-with-me" in mails[0].text and "view and download" in mails[0].text
    assert "%PDF" not in mails[0].text  # never the file itself
