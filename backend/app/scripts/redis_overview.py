"""Show what Redis currently holds, grouped by kind – read-only, prints no secret values.

    docker compose exec backend python -m app.scripts.redis_overview

Redis stores only short-lived security data; every key expires by itself (TTL).
"""

from collections import defaultdict

import redis

from app.core.config import get_settings

# Key prefix -> what it is (see the services that create them).
KINDS = {
    "refresh": "Login sessions (hashed refresh tokens, 7 days)",
    "refresh_used": "Already-rotated refresh tokens (theft detection)",
    "user_sessions": "List of each user's active sessions",
    "access_denylist": "Access tokens blocked by logout (until they expire)",
    "revoked_before": "'Log out everywhere' – tokens before this time are invalid",
    "mfa_challenge": "Logins waiting for the 6-digit code (5 min)",
    "mfa_setup": "Two-step verification being set up (10 min)",
    "pwd_reset": "Password-reset links (hashed, 15 min, single use)",
    "pwd_reset_user": "Latest reset link per user",
    "email_verify": "Email-verification links (hashed, 24 h, single use)",
    "email_verify_user": "Latest verification link per user",
    "oauth_state": "Google logins in progress (10 min)",
    "login_fail": "Failed-login counters",
    "lockout": "Locked accounts (15 min after 5 wrong passwords)",
    "rl": "Rate-limit counters per IP (1 minute)",
}


def human(seconds: int) -> str:
    if seconds < 0:
        return "no expiry"
    if seconds < 120:
        return f"{seconds} s"
    if seconds < 7200:
        return f"{seconds // 60} min"
    if seconds < 172800:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} days"


def main() -> None:
    r = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    groups: dict[str, list[int]] = defaultdict(list)
    for key in r.scan_iter("*"):
        groups[key.split(":", 1)[0]].append(r.ttl(key))

    total = sum(len(ttls) for ttls in groups.values())
    print(f"\nRedis holds {total} keys – all temporary (they delete themselves):\n")
    print(f"{'KIND':<18} {'COUNT':>5}  {'EXPIRES IN':<20} MEANING")
    print("-" * 100)
    for prefix in sorted(groups, key=lambda p: -len(groups[p])):
        ttls = [t for t in groups[prefix] if t >= 0] or [-1]
        low, high = human(min(ttls)), human(max(ttls))
        span = low if low == high else f"{low} – {high}"
        meaning = KINDS.get(prefix, "")
        print(f"{prefix:<18} {len(groups[prefix]):>5}  {span:<20} {meaning}")
    print("\nOnly hashes and ids are stored – never passwords or the raw tokens from emails.\n")


if __name__ == "__main__":
    main()
