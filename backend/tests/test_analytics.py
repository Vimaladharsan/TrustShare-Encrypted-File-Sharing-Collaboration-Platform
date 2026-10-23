"""Favorites, Recent, Storage, File Analytics and My Activity (Milestone 2, Phase 7)."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient

from tests.test_files import PDF, auth, new_user, upload

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
TXT = b"meeting notes\n"


def today_utc() -> str:
    return date.today().isoformat()


def in_days(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


# ---------- storage ----------


def test_storage_report_breaks_usage_down_by_type(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    upload(client, token, "report.pdf", PDF)
    photo = upload(client, token, "photo.png", PNG).json()["id"]
    client.post(f"/api/files/{photo}/trash", headers=auth(token))

    report = client.get("/api/files/storage", headers=auth(token)).json()

    by_type = {row["category"]: row for row in report["by_category"]}
    assert by_type["document"] == {"category": "document", "bytes": len(PDF), "files": 1}
    assert by_type["image"]["bytes"] == len(PNG)  # trash still counts toward the quota
    assert report["used_bytes"] == len(PDF) + len(PNG)
    assert report["trash_bytes"] == len(PNG)
    assert [f["name"] for f in report["largest"]] == ["report.pdf"]  # active files only


# ---------- favorites ----------


def test_star_and_unstar_a_file(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "report.pdf", PDF).json()["id"]

    assert client.put(f"/api/files/{file_id}/favorite", headers=auth(token)).status_code == 204
    client.put(f"/api/files/{file_id}/favorite", headers=auth(token))  # twice is harmless
    favorites = client.get("/api/files/favorites", headers=auth(token)).json()
    listing = client.get("/api/files", headers=auth(token)).json()["items"]
    client.delete(f"/api/files/{file_id}/favorite", headers=auth(token))
    after = client.get("/api/files/favorites", headers=auth(token)).json()

    assert [f["id"] for f in favorites["items"]] == [file_id]
    assert listing[0]["is_favorite"] is True
    assert after["items"] == []


def test_cannot_star_someone_elses_file(client: TestClient, new_email: Callable[[], str]) -> None:
    owner = new_user(client, new_email())
    file_id = upload(client, owner, "report.pdf", PDF).json()["id"]
    stranger = new_user(client, new_email())

    response = client.put(f"/api/files/{file_id}/favorite", headers=auth(stranger))

    assert response.status_code == 404


def test_trashed_favorites_are_hidden(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "report.pdf", PDF).json()["id"]
    client.put(f"/api/files/{file_id}/favorite", headers=auth(token))

    client.post(f"/api/files/{file_id}/trash", headers=auth(token))

    assert client.get("/api/files/favorites", headers=auth(token)).json()["items"] == []


# ---------- recent ----------


def test_recent_files_follow_my_activity(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    first = upload(client, token, "first.pdf", PDF).json()["id"]
    upload(client, token, "second.txt", TXT)

    client.get(f"/api/files/{first}/download", headers=auth(token))  # touched last
    items = client.get("/api/files/recent", headers=auth(token)).json()["items"]

    assert [item["file"]["name"] for item in items] == ["first.pdf", "second.txt"]
    assert items[0]["last_action"] == "file.download"


# ---------- File Analytics ----------


def test_file_analytics_counts_real_activity(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    pdf = upload(client, owner, "report.pdf", PDF).json()["id"]
    upload(client, owner, "photo.png", PNG)
    client.get(f"/api/files/{pdf}/download", headers=auth(owner))
    link = client.post(
        f"/api/files/{pdf}/shares",
        json={"share_type": "link", "permission": "download", "expires_at": in_days(1)},
        headers=auth(owner),
    ).json()["url"]
    client.get(f"/api/s/{link.rsplit('/s/', 1)[1]}/download")  # a link visitor
    friend = new_email()
    new_user(client, friend)
    client.post(
        f"/api/files/{pdf}/shares",
        json={"share_type": "user", "recipient_email": friend},
        headers=auth(owner),
    )

    data = client.get(
        "/api/analytics/me", params={"tz": "UTC", "to": today_utc()}, headers=auth(owner)
    ).json()

    summary = data["summary"]
    assert summary["uploads"] == {"value": 2, "previous": 0}
    assert summary["downloads"] == {"value": 2, "previous": 0}
    assert summary["shares"] == {"value": 2, "previous": 0}
    assert summary["storage_used_bytes"] == len(PDF) + len(PNG)
    assert len(data["uploads_by_day"]) == 30
    day = data["uploads_by_day"][-1]
    assert day["document"] == 1 and day["image"] == 1
    downloads = data["downloads_by_day"][-1]
    assert downloads == {"date": today_utc(), "total": 2, "unique_users": 2, "shared": 1}
    assert data["shares_by_day"][-1] == {"date": today_utc(), "link": 1, "direct": 1}
    assert [d["downloaded_by"] for d in data["recent_downloads"]] == ["Link visitor", "You"]
    assert data["recent_uploads"][0]["name"] == "photo.png"


def test_analytics_only_count_my_own_files(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    other = new_user(client, new_email())
    upload(client, other, "theirs.pdf", PDF)
    me = new_user(client, new_email())

    data = client.get("/api/analytics/me", headers=auth(me)).json()

    assert data["summary"]["uploads"]["value"] == 0
    assert data["recent_uploads"] == []


def test_analytics_validates_range_and_timezone(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())

    bad_tz = client.get("/api/analytics/me", params={"tz": "Mars/Base"}, headers=auth(token))
    reversed_range = client.get(
        "/api/analytics/me", params={"from": "2026-10-10", "to": "2026-10-01"}, headers=auth(token)
    )
    too_long = client.get(
        "/api/analytics/me", params={"from": "2024-01-01", "to": "2026-01-01"}, headers=auth(token)
    )
    custom = client.get(
        "/api/analytics/me",
        params={"from": "2026-10-01", "to": "2026-10-07", "tz": "Asia/Kolkata"},
        headers=auth(token),
    )

    assert bad_tz.json()["error"]["code"] == "INVALID_TIMEZONE"
    assert reversed_range.status_code == 400 and too_long.status_code == 400
    assert custom.status_code == 200 and len(custom.json()["uploads_by_day"]) == 7


def test_legacy_timezone_names_work(client: TestClient, new_email: Callable[[], str]) -> None:
    """Windows browsers report old names like "Asia/Calcutta" (the tzdata package knows them)."""
    token = new_user(client, new_email())

    response = client.get("/api/analytics/me", params={"tz": "Asia/Calcutta"}, headers=auth(token))

    assert response.status_code == 200


# ---------- my activity ----------


def test_my_activity_shows_only_my_events(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    upload(client, token, "report.pdf", PDF)
    other = new_user(client, new_email())
    upload(client, other, "theirs.pdf", PDF)

    everything = client.get("/api/activity/me", headers=auth(token)).json()
    files_only = client.get("/api/activity/me", params={"group": "files"}, headers=auth(token))

    actions = [entry["action"] for entry in everything["items"]]
    assert "file.upload" in actions and "auth.login.success" in actions
    assert all(entry["details"].get("file_name") != "theirs.pdf" for entry in everything["items"])
    assert all(e["action"].startswith("file.") for e in files_only.json()["items"])
