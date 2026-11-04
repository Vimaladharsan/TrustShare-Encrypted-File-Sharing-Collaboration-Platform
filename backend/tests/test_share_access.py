"""Access history per share: who opened, viewed or downloaded it, when, from which device."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.services.share_service import mask_ip
from tests.test_files import auth, new_user
from tests.test_shares import link_token, owner_with_file, share

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)


def history(client: TestClient, token: str, share_id: str):
    return client.get(f"/api/shares/{share_id}/access", headers=auth(token))


def test_link_visits_are_listed_newest_first(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id, permission="download")
    share_id, token = created.json()["id"], link_token(created)
    visitor = {"User-Agent": CHROME_WINDOWS}

    client.get(f"/api/s/{token}", headers=visitor)
    client.get(f"/api/s/{token}", headers=visitor)  # reload: not a new visit
    client.get(f"/api/s/{token}/preview", headers=visitor)
    client.get(f"/api/s/{token}/download", headers=visitor)

    body = history(client, owner, share_id).json()
    assert body["summary"] == {
        "opened": 1,
        "viewed": 1,
        "downloaded": 1,
        "refused": 0,
        "visitors": 1,
    }
    assert [item["event"] for item in body["items"]] == ["downloaded", "viewed", "opened"]
    first = body["items"][0]
    assert first["visitor"] == "Anonymous visitor" and first["visitor_email"] is None
    assert first["device"] == "Chrome on Windows" and first["kind"] == "desktop"


def test_refused_attempts_say_why(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    created = share(client, owner, file_id, permission="view")
    share_id, token = created.json()["id"], link_token(created)

    client.get(f"/api/s/{token}/download")  # view-only link
    client.delete(f"/api/shares/{share_id}", headers=auth(owner))
    client.get(f"/api/s/{token}")  # revoked

    items = history(client, owner, share_id).json()["items"]
    refused = [item["detail"] for item in items if item["event"] == "refused"]
    assert refused == ["share revoked", "download not allowed (view only)"]


def test_direct_share_shows_the_person(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    recipient_email = new_email()
    recipient = new_user(client, recipient_email)
    me = client.get("/api/users/me", headers=auth(recipient)).json()
    share_id = share(
        client,
        owner,
        file_id,
        share_type="user",
        recipient_email=recipient_email,
        permission="download",
    ).json()["id"]

    client.get(f"/api/shares/{share_id}/download", headers=auth(recipient))

    item = history(client, owner, share_id).json()["items"][0]
    assert item["event"] == "downloaded"
    assert item["visitor"] == me["full_name"] and item["visitor_email"] == recipient_email


def test_only_the_owner_sees_the_history(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner, file_id = owner_with_file(client, new_email)
    share_id = share(client, owner, file_id).json()["id"]
    stranger = new_user(client, new_email())

    assert history(client, stranger, share_id).status_code == 404
    assert history(client, owner, share_id).status_code == 200


def test_ip_addresses_are_partly_hidden() -> None:
    assert mask_ip("203.0.113.42") == "203.0.113.x"
    assert mask_ip("2001:db8:85a3:8d3:1319:8a2e:370:7348") == "2001:db8:85a3:8d3:…"
    assert mask_ip(None) is None
