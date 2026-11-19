# Security testing

Security testing of the **live deployment** (https://trustshare-vimal.centralindia.cloudapp.azure.com)
on **19 November 2026**, as part of Milestone 4.

## Summary

| | |
|---|---|
| Tests run against the live site | **104** |
| Passed | **103** |
| Weaknesses found | **1** (low severity) – fixed, see [findings](#findings) |
| Dependency scan (backend + frontend) | **0 known vulnerabilities** |
| Attacks noticed by threat detection | ✅ every attack type raised an alert |
| Automated tests in CI | 318 backend tests, many of them security tests (see [below](#automated-security-tests)) |

| Area | Tests | Passed | Fixed |
|---|---|---|---|
| HTTPS and TLS | 4 | 4 | 0 |
| Security headers | 8 | 8 | 0 |
| Network exposure | 5 | 5 | 0 |
| Information exposure | 11 | 11 | 0 |
| Sessions and tokens | 7 | 7 | 0 |
| Authentication | 8 | 8 | 0 |
| Brute-force protection | 2 | 2 | 0 |
| Access control (RBAC and ownership) | 18 | 18 | 0 |
| Direct sharing | 5 | 5 | 0 |
| Share links | 12 | 12 | 0 |
| File upload validation | 11 | 10 | 1 |
| Injection | 7 | 7 | 0 |
| Error handling | 2 | 2 | 0 |
| Input validation | 2 | 2 | 0 |
| Data protection | 2 | 2 | 0 |

## Scope and method

- **Target:** the production stack exactly as users reach it – Caddy (HTTPS) → FastAPI → PostgreSQL,
  MongoDB, Redis, Azure Blob Storage – on the Azure VM.
- **Accounts:** only dedicated test accounts (`@uicheck.example.com`); no real user's data was
  touched. The attacker is a normal signed-in user, a second user, or an anonymous visitor.
- **Method:** black-box tests through the public internet with a Python script (`httpx`, `ssl`,
  `socket`) – the same requests an attacker could send. Each test states the expected secure
  behaviour and records what the live site actually did. Results were then cross-checked in the
  server logs and the security-event collection.
- **Checklist:** based on the OWASP Top 10 (2021) – broken access control, cryptographic failures,
  injection, insecure design, security misconfiguration, vulnerable components, authentication
  failures, integrity failures, logging and monitoring failures, SSRF.
- **Not in scope:** denial-of-service / load attacks (would harm the shared free VM), attacks on
  Azure itself, social engineering.

| OWASP Top 10 (2021) | Covered by |
|---|---|
| A01 Broken access control | Access control, direct sharing, share links (IDOR, privilege escalation, role tampering) |
| A02 Cryptographic failures | HTTPS / TLS, cookie flags, file decrypted correctly, no keys in responses, [key management](key-management.md) |
| A03 Injection | SQL, NoSQL operator and regex injection; script in file names; HTML in text previews |
| A04 Insecure design | Download limits, link expiry and revoke, enumeration-safe login and reset |
| A05 Security misconfiguration | Headers, open ports, API schema / `.env` / `.git` exposure, CORS, TRACE, error messages |
| A06 Vulnerable components | `pip-audit` and `npm audit` |
| A07 Identification and authentication failures | Token forgery, refresh-token reuse, lockout, rate limits, weak passwords |
| A08 Software and data integrity failures | Signed JWTs (HS256 only, `alg=none` refused); hash-chained audit log (automated tests) |
| A09 Security logging and monitoring failures | Security events raised during the test run (below) |
| A10 Server-side request forgery | Not applicable – the server never fetches URLs supplied by users |

## Findings

| ID | Finding | Severity | Status |
|---|---|---|---|
| F1 | The reverse proxy replaced the backend's stricter `sandbox` Content-Security-Policy on file previews with the normal site policy | Low | 🔧 Fixed |

**F1 – details.** File previews (`/api/files/{id}/preview`) are sent by the backend with
`Content-Security-Policy: sandbox; default-src 'none'`, so a file opened directly can never run
scripts. In production, Caddy's `header` block set the site-wide CSP on *every* response and
overwrote it. Impact was low: previews are still served as `text/plain` / their real type with
`X-Content-Type-Options: nosniff`, and the app shows them through `blob:` URLs, so no script could
run in testing. **Fix:** `caddy/Caddyfile.prod` now uses `?Content-Security-Policy`, which adds the
site policy only when the backend has not set its own.

### Observations (by design, no change needed)

| Observation | Why it is acceptable |
|---|---|
| An old refresh token still works for **10 seconds** after rotation – but only from the **same IP and browser** | Prevents false "token theft" alarms when a page reload or React's double request refreshes twice. From another device it is refused at once (test 32), and after the window it triggers reuse detection, which signs out every session of that login (tests 33–34). |
| The login limit uses fixed one-minute windows, so a burst that crosses a minute boundary can make up to ~20 attempts | Account lockout after 5 wrong passwords (test 44) still stops guessing against any single account; the per-IP limit only slows down spraying. |
| Port 22 (SSH) answered | The test ran from the administrator's own network. During deployment the Azure network rule for SSH was limited to that IP, and password and keyboard-interactive login are disabled on the server (`sshd -T`) – only the private key works. |
| `/.env`, `/.git/config` and `/docs` answer **200** | That is the React app's `index.html` (single-page app fallback) – no file or secret is served; the tests check the body. |

## Threat detection during the test

The attacks were noticed by TrustShare's own monitoring (Milestone 3). Security events recorded
on the live server during the test run:

| Security event | Count | Caused by |
|---|---|---|
| `unauthorized_access` | 49 | Another user / wrong role trying files and admin pages |
| `blocked_request` | 8 | Requests stopped by rate limits and lockout |
| `token_reuse` | 6 | Re-used refresh tokens (theft simulation) |
| `policy_violation` | 6 | Disallowed file types uploaded (`.exe`, `.svg`, double extension) |
| `file_threat` | 4 | Disguised files – content does not match the extension (program renamed to `.pdf`, HTML renamed to `.png`) |
| `multiple_failed_logins`, `repeated_failed_logins` | 4 + 4 | Wrong-password attempts |
| `account_locked` | 4 | The lockout test |
| `repeated_unauthorized_access` | 4 | The access-control tests in a row |
| `revoked_link_abuse` | 2 | Opening a revoked link |
| `suspicious_ip`, `new_device_login` | 1 + 1 | Many failures from one IP; sign-in from the test script |

These appear on the admin **Security Dashboard** and **Suspicious Activity** pages, and the account
owners were notified – exactly as they would be during a real attack.

## Dependency scan

| Part | Tool | Result |
|---|---|---|
| Backend (Python, incl. indirect dependencies) | `pip-audit -r backend/requirements.txt` | No known vulnerabilities |
| Frontend (npm) | `npm audit` | 0 vulnerabilities |

## Automated security tests

The live test complements the automated tests that run in GitHub Actions on every push
(`docker compose exec backend pytest`), which cover in depth what cannot be tested from outside:

- encryption: AES-256-GCM round trip, tampered ciphertext rejected, wrong key rejected, key
  rotation re-wraps file keys, keys never appear in responses or logs;
- RBAC: every role against protected routes; admins can never see file names or contents;
- tokens: expiry, rotation, reuse detection, session revoke, MFA challenge;
- audit log: hash chain verification detects changed or deleted entries;
- detection rules and notifications for each threat type;
- the secure vault: wrong password lockout and extra encryption.

## How to repeat the test

1. Create test accounts on the target (any `@uicheck.example.com` address).
2. Run the request-level checks from this document (each row lists the request and the expected
   answer), or the Postman collections in `postman/` for the API behaviour.
3. Afterwards, remove the accounts:
   `docker compose -f docker-compose.prod.yml exec backend python -m app.scripts.remove_test_accounts uicheck.example.com`.

## All test results

### HTTPS and TLS

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 1 | HTTP is redirected to HTTPS | 301/308 to https:// | 308 → https://trustshare-vimal.centralindia.cloudapp.azure.com/ | ✅ |
| 2 | Old protocol TLS 1.0 refused | handshake fails | refused (SSLError) | ✅ |
| 3 | Old protocol TLS 1.1 refused | handshake fails | refused (SSLError) | ✅ |
| 4 | Trusted certificate, modern TLS | valid chain, TLS 1.2+ | TLSv1.3, TLS_AES_128_GCM_SHA256, issuer Let's Encrypt, valid until Feb 17 09:13:09 2027 GMT | ✅ |

### Security headers

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 5 | strict-transport-security on pages | present with max-age | max-age=31536000; includeSubDomains | ✅ |
| 6 | content-security-policy on pages | present with default-src 'self' | default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline | ✅ |
| 7 | x-frame-options on pages | present with DENY | DENY | ✅ |
| 8 | x-content-type-options on pages | present with nosniff | nosniff | ✅ |
| 9 | referrer-policy on pages | present | strict-origin-when-cross-origin | ✅ |
| 10 | permissions-policy on pages | present | camera=(), microphone=(), geolocation=(), payment=() | ✅ |
| 11 | No Server/X-Powered-By version banner | absent | server=None, x-powered-by=None | ✅ |
| 12 | API responses not cached (Cache-Control) | no-store | no-store | ✅ |

### Network exposure

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 13 | Port 5432 (PostgreSQL) from the internet | closed | closed | ✅ |
| 14 | Port 27017 (MongoDB) from the internet | closed | closed | ✅ |
| 15 | Port 6379 (Redis) from the internet | closed | closed | ✅ |
| 16 | Port 8000 (backend direct) from the internet | closed | closed | ✅ |
| 17 | Port 22 (SSH) from the internet | open (key-only login) | OPEN | ✅ |

### Information exposure

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 18 | /docs does not expose the API schema | no Swagger / OpenAPI | 200, schema=no | ✅ |
| 19 | /openapi.json does not expose the API schema | no Swagger / OpenAPI | 200, schema=no | ✅ |
| 20 | /redoc does not expose the API schema | no Swagger / OpenAPI | 200, schema=no | ✅ |
| 21 | /api/docs does not expose the API schema | no Swagger / OpenAPI | 404, schema=no | ✅ |
| 22 | /api/openapi.json does not expose the API schema | no Swagger / OpenAPI | 404, schema=no | ✅ |
| 23 | /.env is not served | no secrets | 200, secrets=no | ✅ |
| 24 | /.git/config is not served | no secrets | 200, secrets=no | ✅ |
| 25 | /api/.env is not served | no secrets | 404, secrets=no | ✅ |
| 26 | /backend/.env is not served | no secrets | 200, secrets=no | ✅ |
| 27 | TRACE method disabled | 405/404 | 405 | ✅ |
| 28 | CORS: other websites not allowed | no Access-Control-Allow-Origin | 405, ACAO=None | ✅ |

### Sessions and tokens

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 29 | Refresh cookie flags | HttpOnly; Secure; SameSite=Strict; Path=/api/auth | HttpOnly; Path=/api/auth; SameSite=strict; Secure | ✅ |
| 30 | Access token lifetime | 15 minutes | 15 min | ✅ |
| 31 | Refresh rotates the token | 200 + a different cookie | 200, rotated=True | ✅ |
| 32 | Stolen old refresh token used from another device (immediately) | 401 | 401 | ✅ |
| 33 | Old refresh token re-used after the 10 s grace window | 401 | 401 | ✅ |
| 34 | After reuse, the newest token is revoked too (theft protection) | 401 | 401 | ✅ |
| 35 | Refresh token unusable after logout | 401 | 401 | ✅ |

### Authentication

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 36 | No token → protected API | 401 | 401 | ✅ |
| 37 | Garbage token | 401 | 401 | ✅ |
| 38 | Tampered token payload (role → admin, old signature) | 401 | 401 | ✅ |
| 39 | alg=none token (no signature) | 401 | 401 | ✅ |
| 40 | Token signed with a guessed secret | 401 | 401 | ✅ |
| 41 | Expired token (exp in the past) | 401 | 401 | ✅ |
| 42 | Login: wrong password vs unknown email look the same | same status and message | 401/401, "Invalid email or password." / "Invalid email or password." | ✅ |
| 43 | Forgot password: existing vs unknown email look the same | same status and body | 202/202, same body=True | ✅ |

### Brute-force protection

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 44 | 5 wrong passwords lock the account (correct password refused) | 401 ×5 then 429 | [401, 401, 401, 401, 401] then 429 | ✅ |
| 45 | Login rate limit per IP (10/min) | 429 after 10 attempts | first 429 at attempt 11 | ✅ |

### Access control (RBAC and ownership)

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 46 | User → admin user list | 403 | 403 | ✅ |
| 47 | User → /admin/audit | 403 | 403 | ✅ |
| 48 | User → /audit-logs | 403 | 403 | ✅ |
| 49 | User → /security-monitoring/events | 403 | 403 | ✅ |
| 50 | User → /reports/security | 403 | 403 | ✅ |
| 51 | User → /analytics/storage | 403 | 403 | ✅ |
| 52 | User tries to make themselves admin | 403 | 403 | ✅ |
| 53 | Extra 'role' field in profile update is ignored | role stays user | 200, role=user | ✅ |
| 54 | Another user: GET /files/{owner file} | 404 (existence not revealed) | 404 | ✅ |
| 55 | Another user: GET /files/{owner file}/download | 404 (existence not revealed) | 404 | ✅ |
| 56 | Another user: GET /files/{owner file}/preview | 404 (existence not revealed) | 404 | ✅ |
| 57 | Another user: PATCH /files/{owner file} | 404 (existence not revealed) | 404 | ✅ |
| 58 | Another user: POST /files/{owner file}/trash | 404 (existence not revealed) | 404 | ✅ |
| 59 | Another user: DELETE /files/{owner file} | 404 (existence not revealed) | 404 | ✅ |
| 60 | Another user: GET /files/{owner file}/shares | 404 (existence not revealed) | 404 | ✅ |
| 61 | Another user: POST /files/{owner file}/shares | 404 (existence not revealed) | 404 | ✅ |
| 62 | Unknown file ID | 404 | 404 | ✅ |
| 63 | Encoded path traversal in file ID (%2e%2e%2f) | 404/422, no other data | 404 | ✅ |

### Direct sharing

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 64 | Direct share with VIEW permission → download | 403 | 403 | ✅ |
| 65 | Direct share with VIEW permission → preview | 200 | 200 | ✅ |
| 66 | Recipient tries to revoke/alter the owner's share | 403/404 | 404 | ✅ |
| 67 | Recipient reads the owner's access history | 403/404 | 404 | ✅ |
| 68 | Direct share revoked → recipient preview | 403/404/410 | 410 | ✅ |

### Share links

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 69 | Random / guessed link token | 404 | 404 | ✅ |
| 70 | Injection in link token | rejected (404/422) | 422 | ✅ |
| 71 | View-only link → download | 403 | 403 | ✅ |
| 72 | Download limit 1 → second download | 200 then 410 | 200 then 410 | ✅ |
| 73 | Downloaded file is the original (decrypted correctly) | same bytes | identical=True | ✅ |
| 74 | Revoked link | 410 | 410 | ✅ |
| 75 | Revoked link response not cacheable | Cache-Control: no-store | no-store | ✅ |
| 76 | Password link: none / wrong / right | 403 / 403 / 200 | 403 / 403 / 200 | ✅ |
| 77 | Creating a link that is already expired | 422 | 400 | ✅ |
| 78 | Expiry beyond the maximum (400 days) | 422 | 400 | ✅ |
| 79 | File moved to trash → its link | 404/410 | 404 | ✅ |
| 80 | Public link info does not reveal the owner's email or IDs | no email / user id | keys=['can_preview', 'category', 'downloads_left', 'expires_at', 'extension', 'file_name', 'mime_type', 'owner_name', 'permission', 'size_bytes'] | ✅ |

### File upload validation

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 81 | Windows program (.exe) | 415 rejected | 415 | ✅ |
| 82 | Program renamed to .pdf (magic bytes) | 415 rejected | 415 | ✅ |
| 83 | HTML page renamed to .png | 415 rejected | 415 | ✅ |
| 84 | SVG with script | 415 rejected | 415 | ✅ |
| 85 | Double extension | 415 rejected | 415 | ✅ |
| 86 | File over 25 MB | 413 / refused | server stopped the upload (ReadError) – see server log | ✅ |
| 87 | Oversized file not stored | no 'big.pdf' in the account | 0 found (server log: POST /api/files -> 413) | ✅ |
| 88 | Path traversal in file name | stored with a safe name (no ../) | 201, name='passwd.txt' | ✅ |
| 89 | Script in file name | kept as plain text in JSON (React escapes it when shown) | 201, application/json, name='<img src=x onerror=alert(1)>.txt' | ✅ |
| 90 | Text file containing HTML/script → preview | served as text/plain + sandbox CSP + nosniff | text/plain + nosniff, but the proxy replaced the sandbox CSP → **F1, fixed** | 🔧 |
| 91 | Download is forced as attachment | Content-Disposition: attachment | attachment; filename="sec-private-51d7.pdf"; filename*=UTF-8 | ✅ |

### Injection

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 92 | SQL injection in login email | 422 (not an email) | 422 | ✅ |
| 93 | SQL injection in password | 401 | 401 | ✅ |
| 94 | NoSQL operator objects in login | 422 | 422 | ✅ |
| 95 | NoSQL operator in file search | treated as text, 200 with 0 results | 200, 0 results (treated as text) | ✅ |
| 96 | Regex wildcard in search | escaped – does not list every file | 200, 0 results (escaped) | ✅ |
| 97 | Operator in folder_id | rejected or empty | 404 | ✅ |
| 98 | Operator as file ID | 404/422 | 404 | ✅ |

### Error handling

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 99 | Malformed JSON | 422, no stack trace | 422, stack trace=no | ✅ |
| 100 | Unknown API route | 404 JSON, no details | 404 | ✅ |

### Input validation

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 101 | Very long folder name (5000 chars) | 422 | 422 | ✅ |
| 102 | Weak password at sign-up | 422 | 422 | ✅ |

### Data protection

| # | Test | Expected | Result on the live site | |
|---|---|---|---|---|
| 103 | File details contain no keys or storage paths | none | none | ✅ |
| 104 | Profile response has no password hash / MFA secret | none | none | ✅ |

✅ passed · 🔧 weakness found and fixed
