"""Editing an existing share: permission, expiry and download limit – the link stays the same."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import share_row, update_share
from tests.test_files import auth, make_docx, mongo_db, new_user, upload
from tests.test_shares import in_days, link_token, owner_with_file, share


def edit(client: TestClient, token: str, share_id: str, **body):
    return client.patch(f"/api/shares/{share_id}", json=body, headers=auth(token))


def test_extending_an_expired_link_brings_it_back_with_the_same_url(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id)
    share_id, token = created.json()["id"], link_token(created)
    update_share(
        share_id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        reminder_sent_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert client.get(f"/api/s/{token}").status_code == 410

    new_expiry = in_days(10)
    response = edit(client, owner, share_id, expires_at=new_expiry)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert datetime.fromisoformat(body["expires_at"]) == datetime.fromisoformat(new_expiry)
    assert client.get(f"/api/s/{token}").status_code == 200  # same link works again
    row = share_row(share_id)
    assert row.reminder_sent_at is None  # a fresh reminder will come before the new expiry


def test_change_permission_and_download_limit(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id, permission="view")
    share_id, token = created.json()["id"], link_token(created)
    assert client.get(f"/api/s/{token}/download").status_code == 403

    response = edit(client, owner, share_id, permission="download", max_downloads=1)
    assert response.json()["permission"] == "download"
    assert response.json()["max_downloads"] == 1
    assert client.get(f"/api/s/{token}/download").status_code == 200
    assert client.get(f"/api/s/{token}/download").status_code == 410  # limit reached

    # Raising the limit makes a used-up link work again; it can't go below what was used.
    assert edit(client, owner, share_id, max_downloads=3).json()["status"] == "active"
    assert client.get(f"/api/s/{token}/download").status_code == 200
    too_low = edit(client, owner, share_id, max_downloads=1)
    assert too_low.status_code == 400 and too_low.json()["error"]["code"] == "INVALID_LIMIT"

    # Back to view only: downloads stop and the limit is removed.
    view = edit(client, owner, share_id, permission="view").json()
    assert view["permission"] == "view" and view["max_downloads"] is None
    assert client.get(f"/api/s/{token}/download").status_code == 403


def test_link_expiry_rules_still_apply(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    share_id = share(client, owner, file_id).json()["id"]
    for expires_at in (None, in_days(-1), in_days(60)):
        response = edit(client, owner, share_id, expires_at=expires_at)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_EXPIRY"


def test_direct_share_can_drop_its_expiry_and_recipient_is_told(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    share_id = share(
        client,
        owner,
        file_id,
        share_type="user",
        recipient_email=recipient_email,
        permission="view",
        expires_at=in_days(2),
    ).json()["id"]

    response = edit(client, owner, share_id, expires_at=None, permission="download")
    assert response.status_code == 200
    assert response.json()["expires_at"] is None

    received = client.get("/api/shares/received", headers=auth(recipient)).json()["items"]
    assert received[0]["permission"] == "download" and received[0]["expires_at"] is None
    notices = client.get("/api/notifications", headers=auth(recipient)).json()["items"]
    assert notices[0]["title"] == "Your access to a shared file changed"
    assert "view and download, with no expiry" in notices[0]["message"]


def test_edit_is_recorded_and_unchanged_values_are_not(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    share_id = share(client, owner, file_id, permission="view").json()["id"]

    assert edit(client, owner, share_id, permission="view").status_code == 200  # no change
    edit(client, owner, share_id, permission="download", expires_at=in_days(3))

    logs = list(mongo_db()["activity_logs"].find({"action": "share.update", "file_id": file_id}))
    assert len(logs) == 1
    assert logs[0]["details"]["changes"] == "permission, expiry"


def test_only_the_owner_can_edit_and_revoked_shares_are_final(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    share_id = share(client, owner, file_id).json()["id"]
    stranger = new_user(client, new_email())

    assert edit(client, stranger, share_id, expires_at=in_days(3)).status_code == 404

    client.delete(f"/api/shares/{share_id}", headers=auth(owner))
    revoked = edit(client, owner, share_id, expires_at=in_days(3))
    assert revoked.status_code == 409 and revoked.json()["error"]["code"] == "SHARE_REVOKED"


def test_edit_validation(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    docx_id = upload(client, owner, "plan.docx", make_docx()).json()["id"]
    share_id = share(client, owner, docx_id, permission="download").json()["id"]

    # Word files can't be previewed, so they can't become view-only.
    view = edit(client, owner, share_id, permission="view")
    assert view.status_code == 400 and view.json()["error"]["code"] == "VIEW_NOT_SUPPORTED"
    assert edit(client, owner, share_id).status_code == 422  # nothing to change
    assert edit(client, owner, share_id, permission=None).status_code == 422

    # A file in the trash can't have its shares changed.
    client.post(f"/api/files/{docx_id}/trash", headers=auth(owner))
    assert edit(client, owner, share_id, expires_at=in_days(3)).status_code == 404
