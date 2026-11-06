"""My account overview: security score + checklist, and account statistics."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.test_files import PDF, auth, new_user, upload
from tests.test_shares import share


def overview(client: TestClient, token: str) -> dict:
    response = client.get("/api/users/me/overview", headers=auth(token))
    assert response.status_code == 200
    return response.json()


def test_score_is_the_sum_of_passing_checks(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    body = overview(client, new_user(client, new_email()))
    checks = {c["key"]: c for c in body["checks"]}

    assert set(checks) == {
        "two_step", "email_verified", "failed_sign_ins", "backup_codes", "password_age",
        "devices", "vault",
    }  # fmt: skip
    assert sum(c["points"] for c in body["checks"]) == 100
    assert body["score"] == sum(c["points"] for c in body["checks"] if c["ok"])
    # A brand-new account: no two-step, no backup codes, no vault – but a fresh password,
    # one device and no failed sign-ins.
    assert checks["two_step"]["ok"] is False and checks["two_step"]["fix"] == "security"
    assert checks["backup_codes"]["ok"] is False
    assert checks["vault"]["ok"] is False and checks["vault"]["fix"] == "vault"
    assert checks["password_age"]["ok"] is True
    assert checks["devices"]["ok"] is True
    assert checks["failed_sign_ins"]["ok"] is True
    assert body["grade"] in {"strong", "good", "needs_attention"}


def test_failed_sign_ins_lower_the_score(client: TestClient, new_email: Callable[[], str]) -> None:
    email = new_email()
    token = new_user(client, email)
    before = overview(client, token)["score"]

    client.post("/api/auth/login", json={"email": email, "password": "wrong-Passw0rd!"})

    after = overview(client, token)
    check = next(c for c in after["checks"] if c["key"] == "failed_sign_ins")
    assert check["ok"] is False and "1 failed sign-in attempt" in check["detail"]
    assert after["score"] == before - 15


def test_stats(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "plan.pdf", PDF).json()["id"]
    share(client, token, file_id)

    stats = overview(client, token)["stats"]
    assert stats["files"] == 1
    assert stats["storage_used_bytes"] == len(PDF)
    assert stats["storage_quota_bytes"] > 0
    assert stats["active_shares"] == 1
    assert stats["previous_sign_in"]["device"]  # e.g. "Unknown browser on Unknown system"


def test_overview_needs_a_signed_in_user(client: TestClient) -> None:
    assert client.get("/api/users/me/overview").status_code == 401
