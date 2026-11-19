# TrustShare – System Architecture

> Final architecture after Milestones 1–3. Diagrams use Mermaid and render directly on GitHub.
> Related: [database design](database.md) · [encryption and key management](key-management.md) ·
> [API reference](api.md) · [brief coverage](brief-coverage.md).

## Contents

1. [Overview](#1-overview)
2. [Backend structure](#2-backend-structure)
3. [Frontend structure](#3-frontend-structure)
4. [Request flows](#4-request-flows) – registration, sign-in, token refresh, Google sign-in, encrypted
   upload, encrypted download, sharing, key rotation
5. [Monitoring, notifications and detection](#5-monitoring-notifications-and-detection)
6. [Security design](#6-security-design)
7. [Deployment view](#7-deployment-view)
8. [Mapping to the brief's reference architecture](#8-mapping-to-the-briefs-reference-architecture)

## 1. Overview

TrustShare is a three-tier web application behind an HTTPS reverse proxy:

1. **Client** – a React single-page app (Vite, Tailwind CSS). It talks only to the API; it never
   touches a database or the file store.
2. **API** – a FastAPI backend. Every request is authenticated (JWT), authorised (permission check)
   and validated (Pydantic) before any data is touched. Files are encrypted and decrypted here.
3. **Data** – three databases, each used for what it does best, plus private object storage that
   only ever holds ciphertext.

```mermaid
flowchart LR
    U["Browser<br/>React SPA"]
    C["Caddy<br/>TLS 1.3 reverse proxy"]
    G["Google<br/>OAuth 2.0 / OIDC"]
    M["Gmail SMTP"]

    subgraph API["FastAPI backend (Uvicorn)"]
        direction TB
        MW["Middleware<br/>request ID · security headers · CORS · errors"]
        R["Routes<br/>auth · users · files · folders · trash · vault · shares · admin ·<br/>activity monitoring · audit · notifications · reports · analytics"]
        D["Dependencies<br/>get_current_user · require_permission() · rate limits"]
        S["Services<br/>auth · MFA · files · sharing · vault · encryption · notifications · detection"]
        RP["Repositories"]
        ST["SecureFileStore<br/>encrypt on write · verify + decrypt on read"]
        MW --> R --> D --> S --> RP
        S --> ST
    end

    PG[("PostgreSQL<br/>users · roles · permissions · shares ·<br/>wrapped file keys · vaults")]
    MO[("MongoDB<br/>file metadata · folders · activity + audit logs ·<br/>security events · notifications")]
    RE[("Redis<br/>sessions · one-time tokens · rate limits ·<br/>detection windows · pub/sub")]
    OS[["Object storage<br/>Azure Blob or S3 (RustFS locally)<br/>ciphertext only"]]

    U -- "HTTPS" --> C
    C -- "/api" --> MW
    C -- "pages" --> FE["React app"]
    U -. "redirect" .-> G
    G -. "callback" .-> R
    S -. "SMTP/TLS" .-> M
    RP --> PG
    RP --> MO
    S --> RE
    ST --> OS
```

### Why three databases?

| Store | Holds | Why this store |
|---|---|---|
| **PostgreSQL** | Users, roles, permissions, OAuth links, MFA backup codes, shares, wrapped file keys, vaults | Data that must be **consistent and relational**: unique emails, foreign keys, transactions, constraints (e.g. a download limit counted atomically). A wrong row here is a security bug. |
| **MongoDB** | File and folder metadata, activity logs, hash-chained audit logs, security events, notifications, vault file metadata | **High-volume, flexible documents.** Logs are append-only and grow fast; metadata varies by file type. The Milestone 1 brief requires file metadata in MongoDB. |
| **Redis** | Refresh-token sessions, verification / reset / MFA / OAuth-state tokens (hashed), rate limits, lockouts, detection windows, pub/sub for real-time events | Data that is **temporary and read on every request** – kept in memory and deleted automatically with a TTL. |

**Separation of secrets:** encrypted bytes (object storage), metadata (MongoDB) and keys
(PostgreSQL, wrapped by master keys held only in the backend's environment) live in different
places, so no single store reveals a file. Schema details: [database.md](database.md).

## 2. Backend structure

```
backend/app/
├── main.py                # app, middleware, routers, lifespan (connect databases, start scheduler)
├── core/                  # settings, security (bcrypt, JWT), permissions, errors, logging, middleware, rate limits
├── db/                    # PostgreSQL (SQLAlchemy async), MongoDB, Redis connections
├── models/                # SQLAlchemy models (PostgreSQL tables)
├── schemas/               # Pydantic request / response models
├── repositories/          # data access only – no business rules
├── services/              # business rules: auth, MFA, OAuth, files, folders, trash, sharing, vault,
│                          #   encryption, analytics, security events, email, account deletion
├── crypto/                # master-key keyring (wraps / unwraps file keys), vault key derivation
├── storage/               # object storage adapters (S3, Azure Blob) + SecureFileStore
├── activity_monitoring/   # record_activity() – one recording function for every action; live feed
├── audit/                 # hash-chained audit_logs: filters, verify, CSV
├── security_monitoring/   # detection rules, alert workflow
├── notifications/         # notifications, triggers, SSE stream, background scheduler
├── reports/               # upload / download / sharing / user / security reports
├── analytics/             # admin storage analytics
├── api/                   # deps.py (get_current_user, require_permission) and routes/
└── scripts/               # create_admin, seed_demo, rotate_keys, copy_objects, remove_test_accounts …
```

**Rule:** routes handle HTTP only (parse, call a service, return a schema); services make every
decision; repositories only read and write. Every security decision therefore lives in one
testable place. Milestone 3 modules are named like the brief.

## 3. Frontend structure

```
frontend/src/
├── api/             # Axios client + one module per backend area
├── auth/            # AuthProvider: session resume, sign-in, MFA step, sign-out
├── notifications/   # NotificationsProvider: SSE stream, unread count, desktop pop-ups
├── theme/           # light / dark / system theme
├── components/      # layouts (workspace, admin console), file table, dialogs, charts …
└── pages/           # workspace pages, admin pages, public share page, auth pages
```

- **Access token in memory only** (never localStorage). The Axios client refreshes it once on a
  `401` and retries; concurrent requests share one refresh (a reused refresh token would end every
  session).
- **Permission-aware UI:** buttons and menus follow the user's permissions from `/api/users/me` –
  a convenience only; the backend enforces everything.
- **Two layouts:** the light/dark user workspace and a separate dark admin console, so admin mode is
  never mistaken for the workspace.
- Every page has loading, empty and error states and works at phone width.

## 4. Request flows

### 4.1 Registration and email verification

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as React
    participant API as FastAPI
    participant PG as PostgreSQL
    participant R as Redis
    participant MAIL as Gmail SMTP
    participant MO as MongoDB

    U->>FE: Fill sign-up form
    FE->>API: POST /api/auth/register {name, email, password}
    API->>API: Validate (Pydantic + password policy)
    API->>PG: SELECT user by email
    alt email already exists
        API->>MAIL: Send "you already have an account" notice to the owner
        API-->>FE: 202 (same response, no user enumeration)
    else new email
        API->>API: bcrypt.hash(password, cost 12)
        API->>PG: INSERT user (role = user, verified = false)
        API->>R: SET email_verify:{sha256(token)} = user_id, TTL 24h
        API->>MAIL: Send link /verify-email?token=...
        API->>MO: activity_logs ← auth.register
        API-->>FE: 202 "Check your email" (same message as above)
    end
    U->>FE: Click link in email
    FE->>API: POST /api/auth/verify-email {token}
    API->>R: GETDEL email_verify:{sha256(token)}
    API->>PG: UPDATE user SET is_email_verified = true
    API-->>FE: 200
```

### 4.2 Sign-in with two-step verification, JWT and permission check

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as React
    participant API as FastAPI
    participant PG as PostgreSQL
    participant R as Redis
    participant MO as MongoDB

    FE->>API: POST /api/auth/login {email, password}
    API->>R: rate-limit + lockout check
    API->>PG: SELECT user + role + permissions
    API->>API: bcrypt.verify(password, hash)
    alt wrong password
        API->>R: INCR login_fail:{user_id} (5 → lockout 15 min)
        API->>MO: activity_logs ← auth.login.failed
        API-->>FE: 401 "Invalid email or password"
    else MFA enabled
        API->>R: SET mfa_challenge:{id} = user_id, TTL 5 min
        API-->>FE: 200 {mfa_required: true, challenge_id}
        FE->>API: POST /api/auth/mfa/verify {challenge_id, code}
        API->>API: pyotp verify (±30 s window, no code reuse)
    end
    API->>API: create access JWT (sub, role, perms, exp 15 min)
    API->>R: SET refresh:{sha256(token)} (user, family, ip, ua), TTL 7 days
    API->>R: SADD user_sessions:{user_id} token hash
    API->>MO: activity_logs ← auth.login.success
    API-->>FE: 200 {access_token} + Set-Cookie refresh_token (HttpOnly, SameSite=Strict)

    Note over FE,API: Later – a protected request
    FE->>API: GET /api/admin/users  (Authorization: Bearer <JWT>)
    API->>API: verify signature + expiry → load user → require_permission("user:read")
    alt role = user
        API-->>FE: 403 Forbidden
    else role = admin
        API-->>FE: 200 [users]
    end
```

### 4.3 Token refresh, devices and sign-out

```mermaid
sequenceDiagram
    autonumber
    participant FE as React (Axios interceptor)
    participant API as FastAPI
    participant R as Redis

    FE->>API: any request → 401 (access token expired)
    FE->>API: POST /api/auth/refresh (cookie: refresh_token)
    API->>API: hash the refresh token
    API->>R: GETDEL refresh:{sha256(token)}
    alt key found (normal case)
        API->>R: SET refresh:{sha256(new token)}, TTL 7 days (same family)
        API-->>FE: new access token + new refresh cookie
        FE->>API: retry original request
    else key missing (token already used → likely stolen)
        API->>R: delete every session in user_sessions:{user_id}
        API-->>FE: 401 → frontend redirects to login
    end
```

**Devices and per-device sign-out.** Every login starts a *session* (the refresh-token family, a random id). The id goes into each access token as the `sid` claim, and each refresh record keeps the browser, IP and `signed_in_at`. `GET /users/me/sessions` groups the refresh records by family (newest one wins) and marks the one matching the caller's `sid` as *This device*. `DELETE /users/me/sessions/{id}` deletes that family's refresh records and sets `revoked_sid:{id}` in Redis for 15 minutes (the access-token lifetime), so the signed-out device's access token is rejected on its very next request instead of working until it expires.

### 4.4 Google sign-in (OAuth 2.0 Authorization Code flow)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as React
    participant API as FastAPI
    participant R as Redis
    participant GG as Google
    participant PG as PostgreSQL

    U->>FE: Click "Continue with Google"
    FE->>API: GET /api/auth/google/login
    API->>R: SET oauth_state:{state}, TTL 10 min (CSRF protection)
    API-->>U: 302 → accounts.google.com (client_id, scope openid email profile, state)
    U->>GG: Sign in & consent
    GG-->>API: 302 /api/auth/google/callback?code&state
    API->>R: GETDEL oauth_state:{state} (must exist)
    API->>GG: exchange code → ID token, verify signature, audience and email_verified
    API->>PG: find oauth_account(google, sub) → else user by email → else create user
    API->>R: create refresh session (same as normal login)
    API-->>U: 302 → frontend /auth/callback (refresh cookie set) → frontend calls /auth/refresh
```

If the linked account has MFA enabled, the callback redirects to the MFA step instead of finishing the login.

Implementation notes: the authorization request also uses **PKCE** (S256; the code verifier is stored with the state in Redis), the ID token signature is checked against Google's published keys (`aud` = our client id, `iss` = Google), and errors (cancelled, expired state, unverified Google email, disabled account) redirect to `/login?oauth_error=…`.

### 4.5 Encrypted upload

Validation (permission `file:upload`, type allow-list, magic bytes and Office structure, 25 MB
streamed limit, quota, SHA-256) happens before encryption.

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant API as FastAPI
    participant ENC as EncryptionService + Keyring
    participant S3 as Object storage (RustFS / S3)
    participant PG as PostgreSQL
    participant MO as MongoDB

    U->>API: POST /api/files (multipart, JWT)
    API->>API: Permission file:upload, type allow-list, size, quota, magic bytes, SHA-256
    API->>ENC: new random DEK (256-bit)
    ENC->>ENC: encrypt 1 MiB chunks with AES-256-GCM (nonce = prefix + counter + last flag, AAD = file id + index)
    API->>S3: PUT encrypted object (private bucket, random key)
    ENC->>ENC: wrap DEK with active KEK (version n)
    API->>PG: INSERT file_keys(file_id, wrapped_key, key_version)
    API->>MO: files: metadata + encryption {algorithm, format, chunk_size, encrypted_size}
    API->>MO: activity_logs: file.upload
    API-->>U: 201 file info (no key material)
```

The plaintext never reaches object storage; the raw DEK never leaves backend memory.

Rejected cases return clear errors with a machine-readable code: **415** `UNSUPPORTED_FILE_TYPE`, **413** `FILE_TOO_LARGE`, **413** `QUOTA_EXCEEDED`, **409** `DUPLICATE_FILE` (the UI offers "keep both"). A rejected upload's temp file is deleted immediately.

### 4.6 Encrypted download and preview

```mermaid
sequenceDiagram
    autonumber
    actor U as User or link visitor
    participant API as FastAPI
    participant PG as PostgreSQL
    participant S3 as Object storage
    participant ENC as EncryptionService + Keyring
    participant MO as MongoDB

    U->>API: GET /api/files/{id}/download (or /api/s/{token}/download)
    API->>API: Authenticate and authorize: owner, direct share or valid link (permission, expiry, revoked, limit)
    API->>PG: SELECT file_keys WHERE file_id
    ENC->>ENC: unwrap DEK with the KEK of the stored version
    API->>S3: GET encrypted object (streamed)
    loop each chunk
        ENC->>ENC: decrypt and verify GCM tag (fail: stop, security event)
        API-->>U: verified plaintext chunk
    end
    API->>MO: activity_logs: file.download {via: owner | direct_share | link}
```

### 4.7 Sharing

```mermaid
sequenceDiagram
    autonumber
    actor O as Owner
    actor R as Recipient
    participant API as FastAPI
    participant PG as PostgreSQL

    O->>API: POST /api/files/{id}/shares {type, permission, expires_at, max_downloads, recipient_email}
    API->>API: owner + share:create, file active, expiry in the future
    alt link share
        API->>API: token = 256-bit random (URL-safe)
        API->>PG: INSERT shares(token_hash = sha256(token), ...)
        API-->>O: link https://.../s/{token} (token shown once)
    else direct share
        API->>PG: INSERT shares(recipient_id, ...)
        API-->>O: 201 (recipient sees it under "Shared with Me")
    end
    R->>API: GET /api/s/{token} (or the file in "Shared with Me")
    API->>PG: find share by sha256(token) / recipient
    API->>API: deny if revoked, expired, limit reached, file trashed/deleted, owner disabled, owner lost share:create, action not permitted
    API-->>R: file info / preview (view) / download (download) - decrypted as in 8.3
```

| Situation | Result |
|---|---|
| Owner requests own file | Allowed (account active, file active) |
| Valid share, permitted action | Allowed – only that action (`view` = preview, `download` = preview + download) |
| Action not allowed by the permission (e.g. download on a view-only share) | 403 `SHARE_DOWNLOAD_NOT_ALLOWED` |
| Not the recipient of a direct share (incl. Admins) | 404 – nothing revealed |
| Link expired or revoked | 410 Gone ("This link has expired" / "This link was revoked") |
| Download limit reached | 410 Gone |
| File trashed, owner disabled or owner lost `share:create` | 404 – the link stops working automatically (works again if the file is restored and the link is still valid) |
| File deleted forever | 404 – its shares are deleted together with the object and key |

Link tokens: 256-bit random (`secrets.token_urlsafe(32)`), only the SHA-256 is stored, the full link is shown once; request logs print `/api/s/***`; the share page sets `Referrer-Policy: no-referrer`; public endpoints are rate-limited per IP (`SHARE_LINK_RATE_LIMIT_PER_MINUTE`). Download limits are counted with one atomic `UPDATE … WHERE download_count < max_downloads`, so two visitors can't both take the last download. Links must expire within `SHARE_LINK_MAX_DAYS` (30); direct shares may have no expiry.

Edits (`PATCH /api/shares/{id}`) keep the same link; optional link passwords are bcrypt-hashed and
sent in the `X-Share-Password` header; every open, view, download and refused attempt is recorded
for the share's access history.

### 4.8 Key rotation

Admin adds master key `v(n+1)` → sets it active → runs `rotate_keys` → every `file_keys` row on an older
version is unwrapped and re-wrapped with the new key (batches, idempotent) → old KEK removed when unused.
Files are never re-encrypted; downloads keep working during rotation.

Details: [key-management.md](key-management.md).

## 5. Monitoring, notifications and detection

### 5.1 Modules

| Module | Responsibility |
|---|---|
| `app/activity_monitoring/` | `record_activity()` – the one reusable recording function; admin feed, summary, live stream |
| `app/audit/` | Append-only, hash-chained `audit_logs`; retrieval, filters, verification, CSV |
| `app/security_monitoring/` | `detection.py` rule engine; alert summary, filters and workflow |
| `app/notifications/` | Notifications + preferences, triggers, SSE stream, background scheduler, emails |
| `app/reports/` | Upload, download, sharing, user-activity and security reports (+ CSV) |
| `app/analytics/` | Admin storage analytics; shared query helpers (filters, file metadata without names) |

M1/M2 code stays layered (routes → services → repositories); `ActivityService.log` now simply delegates to
`record_activity`, so every existing call site feeds monitoring, audit, detection and notifications.

### 5.2 Event flow

```mermaid
flowchart LR
    A[Any action<br/>login · upload · download · share · denied access] --> R[record_activity]
    R --> L[(activity_logs<br/>feed + own history)]
    R --> AU[(audit_logs<br/>seq · prev_hash · hash)]
    R --> P[[Redis pub/sub<br/>activity_feed]] --> F[Admin live feed - SSE]
    R --> D{Detection rules<br/>Redis sliding windows}
    D -- limit exceeded --> E[(security_events<br/>alert: severity, status)]
    E --> N[Notifications]
    R --> N
    N --> NC[(notifications)]
    N --> PS[[Redis pub/sub<br/>notifications:user]] --> B[Bell - SSE, real time]
    N --> M[Email - Gmail SMTP<br/>per preferences]
    S[Scheduler every 5 min<br/>Redis lock] --> N
    S --> R
```

### 5.3 Design decisions

- **Tamper-evident audit log.** `hash = SHA-256(prev_hash + canonical entry)`; a unique index on `seq` makes
  concurrent writers retry instead of forking the chain. `GET /api/audit-logs/verify` re-computes every hash and
  names the first broken entry. History recorded before M3 was imported once (`import_audit_history`, flagged
  `imported`).
- **Detection.** Each rule counts matching activities per subject (account, user or IP) in a Redis sorted set
  scored by time; above the limit → one security event, then a cooldown for the rest of the window. Thresholds
  come from `.env`. Every security event is also an alert with a status (open → acknowledged → resolved).
- **Real-time delivery with Server-Sent Events.** One long-lived response per tab, fed by Redis pub/sub. The
  browser reads it with `fetch` and the in-memory access token in the Authorization header (no token in the URL).
  The server ends the stream with `reauth` when the token expires or the device is signed out, the client
  refreshes and reconnects; a heartbeat every 25 s keeps proxies (Caddy) from closing it.
- **Background scheduler.** A task started with the API (Redis lock → only one copy runs) sends expiry reminders
  24 h before a share expires and records `share.expired` once.
- **Privacy.** Admin reports, analytics, logs and alerts return file IDs, types and sizes – never names
  (`activity_monitoring.models.redact`, name-free audit descriptions). This is a deliberate deviation from the
  brief's "filter by file name", in line with the M2 rule that admins cannot see users' files.
- **Storage of file metadata.** The brief assumes file metadata in PostgreSQL; TrustShare keeps it in MongoDB
  (Milestone 1 requirement), so analytics read MongoDB `files`/`vault_files` and PostgreSQL `users`/`shares`.

### 5.4 Admin console

Overview · **Monitoring** (user activity with live feed, audit logs with integrity banner, security
monitoring, suspicious-activity alerts) · **Reports & analytics** (file activity reports, storage
analytics) · **Management** (users, notifications, system). Every admin endpoint requires
`audit:read` or `user:read` / `user:manage` on the backend; the hidden menu is only a convenience.

## 6. Security design

| Threat | Control |
|---|---|
| Storage or database leak | Files encrypted with AES-256-GCM, one key per file; keys stored only wrapped by master keys kept outside the databases; vault files sealed again with a key from the vault password |
| Tampered files | Authenticated encryption per chunk; any changed, missing or reordered chunk stops the download and raises a security event |
| Tampered logs | Audit entries hash-chained (SHA-256); verification names the first broken entry |
| Password database leak | bcrypt (cost 12, salted); passwords never logged |
| Token theft | Access token 15 min, in memory only; refresh token HttpOnly + SameSite cookie, rotated on every use, reuse ends every session; per-device sign-out takes effect immediately |
| Brute force / credential stuffing | Per-IP rate limits, lockout after 5 failures, two-step verification, brute-force detection alerting admins |
| Account enumeration | Same answer for existing and unknown emails on registration, sign-in and password reset |
| Privilege escalation | Permission checked on every route; ownership checked in services; other users' files answer `404`; role can't be chosen at registration; admins have no file permission over other users |
| Link guessing or leaks | 256-bit random tokens stored only as hashes and masked in logs; expiry, download limits, optional password, instant revoke; every access re-checked |
| Malicious uploads | Allow-list + magic-byte and Office-structure check, streamed size limit, random stored names; downloads as attachments; previews only for safe types, sandboxed |
| Interception | TLS 1.3 through Caddy |
| Cached sensitive responses | `Cache-Control: no-store` on every API response |
| Clickjacking / MIME sniffing | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` |
| CSRF on OAuth | Random `state` (single use) + PKCE |
| Secrets in code | `.env` (gitignored), `.env.example` documents every key |

## 7. Deployment view

Local development and the current setup: one `docker compose` project with **7 services**.

```mermaid
flowchart TB
    subgraph host["docker compose"]
        CA["caddy<br/>:8443 HTTPS"]
        FE["frontend<br/>Vite :5173"]
        BE["backend<br/>python:3.12-slim · Uvicorn :8000"]
        PG[("postgres:16")]
        MO[("mongo:7")]
        RE[("redis:7")]
        RF[["rustfs<br/>S3-compatible, local"]]
    end
    AZ[["Azure Blob Storage<br/>(STORAGE_PROVIDER=azure)"]]
    CA --> FE
    CA --> BE
    BE --> PG
    BE --> MO
    BE --> RE
    BE --> RF
    BE -.-> AZ
```

All services have health checks; the backend waits for the databases and runs migrations on start.
Uvicorn trusts `X-Forwarded-For` only from proxies inside the Docker network, so logs and rate
limits see the visitor's real IP. Production runs the same stack with `docker-compose.prod.yml` on an Azure VM –
see the [deployment guide](deployment.md).

## 8. Mapping to the brief's reference architecture

| Brief component | TrustShare |
|---|---|
| Web app (React / Next.js), admin dashboard | React + Vite SPA with a separate admin console |
| API gateway: SSL termination, routing | Caddy |
| Gateway: authentication, validation, rate limiting, audit logging | FastAPI dependencies and middleware |
| Auth, file, encryption, sharing, notification, analytics services | Backend modules (sections 2 and 5) |
| Message queue / event bus | Redis pub/sub and an in-process scheduler |
| PostgreSQL, MongoDB, Redis, encrypted storage, audit logs | As in section 1 |
| Docker, CI/CD | Docker Compose, GitHub Actions |
| AWS / Azure | Azure Blob Storage for files; cloud hosting in Milestone 4 |
| Kubernetes, SIEM / IDS, ML anomaly detection, mobile / desktop apps, FCM, captcha | Future work |

Item-by-item coverage: [brief-coverage.md](brief-coverage.md).
