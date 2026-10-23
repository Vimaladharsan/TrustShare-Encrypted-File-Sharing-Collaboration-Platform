# TrustShare – System Architecture

> Diagrams use Mermaid and render directly on GitHub and in VS Code (Markdown Preview Mermaid Support extension).

## 1. Overview

TrustShare is a three-tier web application:

1. **Client** – a React single-page app (Vite + Tailwind). It only talks to the backend over HTTPS; it never touches a database or the file store.
2. **API** – a FastAPI backend. Every request is authenticated (JWT), authorised (permission check) and validated (Pydantic) before any data is touched.
3. **Data** – three databases, each chosen for what it is good at, plus a file store behind an interface.

```mermaid
flowchart LR
    U["👤 Browser<br/>React + Vite + Tailwind"]
    G["Google OAuth 2.0<br/>(OpenID Connect)"]
    M["Gmail SMTP<br/>(verification / reset emails)"]

    subgraph API["FastAPI backend (Uvicorn)"]
        direction TB
        MW["Middleware<br/>CORS · request ID · rate limit · error handler"]
        R["Routers<br/>/auth /users /admin /files /folders /activity /health"]
        D["Dependencies<br/>get_current_user · require_permission()"]
        S["Services<br/>AuthService · MfaService · FileService · FolderService · ActivityService"]
        RP["Repositories<br/>UserRepo (SQL) · FileRepo / FolderRepo / ActivityRepo (Mongo)"]
        ST["StorageBackend<br/>LocalStorage (M1) → EncryptedS3Storage (M2)"]
        MW --> R --> D --> S --> RP
        S --> ST
    end

    PG[("PostgreSQL 16<br/>users · roles · permissions<br/>oauth accounts · MFA backup codes")]
    MO[("MongoDB 7<br/>files · folders · activity_logs")]
    RE[("Redis 7<br/>refresh sessions · one-time tokens<br/>rate limits · lockouts")]
    FS[["File store<br/>./storage (M1)<br/>AWS S3, AES-256-GCM (M2)"]]

    U -- "HTTPS · JSON · Bearer JWT" --> MW
    U -. "redirect" .-> G
    G -. "callback with code" .-> R
    S -. "SMTP/TLS" .-> M
    RP --> PG
    RP --> MO
    S --> RE
    ST --> FS
```

### Why three databases?

| Store | Holds | Why this store |
|---|---|---|
| **PostgreSQL** | Users, roles, permissions, OAuth links, MFA backup codes. **(M2)** share links and permission grants. | Data that must be **consistent and relational**: unique emails, foreign keys (user → role), transactions. A wrong row here is a security bug, so we want strict schema and constraints. |
| **MongoDB** | File metadata, folders, activity/audit logs. | **High-volume, flexible documents**. File metadata varies by type (an image has dimensions, a PDF has page count, M2 adds encryption fields) – no migrations needed. Activity logs are append-only and grow fast. The M1 brief requires file metadata in MongoDB. |
| **Redis** | Refresh-token sessions, email-verify / reset / MFA-challenge tokens, rate-limit counters, lockouts. | Data that is **temporary and read on every request**. Redis keeps it in memory (sub-millisecond) and deletes it automatically with a **TTL**, so expired tokens clean themselves up. |

The detailed schema is in [database.md](database.md).

## 2. Backend layering

```
backend/app/
├── main.py            # create app, middleware, routers, lifespan (connect / disconnect DBs)
├── core/              # config (pydantic-settings), security (bcrypt, JWT), logging, errors
├── db/                # postgres.py (SQLAlchemy async engine), mongo.py (Motor), redis.py
├── models/            # SQLAlchemy ORM models (PostgreSQL tables)
├── schemas/           # Pydantic request / response models
├── repositories/      # data access only – no business rules
├── services/          # business rules – auth, MFA, OAuth, files, folders, activity, email
├── storage/           # StorageBackend interface + LocalStorage
├── api/
│   ├── deps.py        # get_current_user, require_permission("file:upload")
│   └── routes/        # auth.py, users.py, admin.py, files.py, folders.py, activity.py, health.py
└── tests/
```

**Rule:** routers handle HTTP only (parse, call a service, return a schema); services contain all decisions; repositories only read and write. This keeps every security decision in one testable place.

## 3. Request flows

### 3.1 Registration and email verification

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

### 3.2 Login with MFA, JWT issue and role check

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
    API->>R: SET refresh:{jti} (user, family, ip, ua), TTL 7 days
    API->>R: SADD user_sessions:{user_id} jti
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

### 3.3 Token refresh (rotation + reuse detection)

```mermaid
sequenceDiagram
    autonumber
    participant FE as React (Axios interceptor)
    participant API as FastAPI
    participant R as Redis

    FE->>API: any request → 401 (access token expired)
    FE->>API: POST /api/auth/refresh (cookie: refresh_token)
    API->>API: verify refresh JWT signature → jti
    API->>R: GETDEL refresh:{jti}
    alt key found (normal case)
        API->>R: SET refresh:{new_jti}, TTL 7 days (same family)
        API-->>FE: new access token + new refresh cookie
        FE->>API: retry original request
    else key missing (token already used → likely stolen)
        API->>R: delete every session in user_sessions:{user_id}
        API-->>FE: 401 → frontend redirects to login
    end
```

### 3.4 File upload

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as React
    participant API as FastAPI
    participant ST as StorageBackend (LocalStorage)
    participant MO as MongoDB

    U->>FE: Drop file in upload modal
    FE->>API: POST /api/files (multipart, folder_id) – progress via Axios onUploadProgress
    API->>API: require_permission("file:upload")  (Guest → 403)
    API->>MO: folder exists & belongs to user?
    API->>MO: current usage (sum of size_bytes) vs quota
    API->>API: read first 2 KB → magic-byte type detection + extension must match allow-list
    loop stream in 1 MB chunks
        API->>API: running size > 25 MB? → abort 413
        API->>API: update SHA-256
        API->>ST: write chunk to temp file
    end
    API->>ST: move temp file → storage/{user_id}/{uuid} (random name)
    API->>MO: INSERT files {original_name, size, mime, sha256, owner_id, folder_id, storage_key, ...}
    API->>MO: activity_logs ← file.upload
    API-->>FE: 201 {file metadata}
    FE->>FE: refresh list + toast "Uploaded"
```

Rejected cases return clear errors with a machine-readable code: **415** `UNSUPPORTED_FILE_TYPE`, **413** `FILE_TOO_LARGE`, **413** `QUOTA_EXCEEDED`, **409** `DUPLICATE_FILE` (the UI offers "keep both"). A rejected upload's temp file is deleted immediately.

### 3.5 Google login (OAuth 2.0 Authorization Code flow)

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
    API->>GG: exchange code → ID token; verify signature, audience, email_verified
    API->>PG: find oauth_account(google, sub) → else user by email → else create user
    API->>R: create refresh session (same as normal login)
    API-->>U: 302 → frontend /auth/callback (refresh cookie set) → frontend calls /auth/refresh
```

If the linked account has MFA enabled, the callback redirects to the MFA step instead of finishing the login.

Implementation notes: the authorization request also uses **PKCE** (S256; the code verifier is stored with the state in Redis), the ID token signature is checked against Google's published keys (`aud` = our client id, `iss` = Google), and errors (cancelled, expired state, unverified Google email, disabled account) redirect to `/login?oauth_error=…`.

## 4. API surface (Milestone 1)

All routes are under `/api`. Interactive docs: `http://localhost:8000/docs`.

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/health` | public | Status of PostgreSQL, MongoDB, Redis |
| POST | `/auth/register` | public | Create account, send verification email |
| POST | `/auth/verify-email` | public | Confirm email with token |
| POST | `/auth/verify-email/resend` | logged in | Send a new verification link (soft mode by default: unverified users can log in; `REQUIRE_EMAIL_VERIFICATION=true` blocks them) |
| POST | `/auth/resend-verification` | public | Resend link (rate-limited) |
| POST | `/auth/login` | public | Password login → tokens or MFA challenge |
| POST | `/auth/mfa/verify` | public (challenge) | Second step with TOTP or backup code |
| POST | `/auth/refresh` | refresh cookie | Rotate refresh token, new access token |
| POST | `/auth/logout` | logged in | Revoke current session |
| POST | `/auth/logout-all` | logged in | Revoke all sessions |
| POST | `/auth/forgot-password` | public | Email reset link (always 202, same answer for unknown emails) |
| POST | `/auth/reset-password` | public (token) | Set new password, revoke sessions |
| GET | `/auth/google/login` · `/auth/google/callback` | public | Google OAuth |
| GET | `/users/me` | logged in | Profile, role, permissions, storage usage |
| PATCH | `/users/me` | logged in | Update name |
| POST | `/users/me/password` | logged in | Change password |
| POST | `/users/me/mfa/setup` · `/mfa/enable` · `/mfa/disable` · `/mfa/backup-codes` | logged in | Manage TOTP |
| GET | `/admin/users` | `user:read` | List/search users |
| PATCH | `/admin/users/{id}` | `user:manage` | Change role, activate/deactivate (not yourself; never the last admin) |
| POST | `/admin/users/{id}/unlock` | `user:manage` | Clear a login lockout early |
| GET | `/folders` · POST `/folders` | `file:read` · `folder:manage` | List children / create |
| PATCH · DELETE | `/folders/{id}` | `folder:manage` | Rename, move, trash |
| GET | `/folders/{id}/breadcrumbs` | `file:read` | Path to root |
| GET | `/files` | `file:read` | List with `folder_id, q, category, sort, order, page, trashed` |
| POST | `/files` | `file:upload` | Upload (multipart) |
| GET | `/files/{id}` · `/files/{id}/download` · `/files/{id}/preview` | `file:read` | Metadata / download / inline preview |
| PATCH | `/files/{id}` | `file:update` | Rename, move |
| POST | `/files/{id}/trash` · `/files/{id}/restore` | `file:update` | Soft delete / restore |
| DELETE | `/files/{id}` | `file:delete` | Permanent delete |
| GET | `/activity` | logged in (own) / `audit:read` (all) | Activity log |

**Error format** (every error):
```json
{ "error": { "code": "FILE_TOO_LARGE", "message": "File exceeds the 25 MB limit.", "request_id": "b1f2…" } }
```

## 5. Security design (M1)

| Threat | Control |
|---|---|
| Password database leak | bcrypt (cost 12, salted); passwords never logged. |
| Token theft | Access token lives 15 min in memory only (not localStorage); refresh token in **HttpOnly, SameSite=Strict** cookie, rotated on each use, reuse → revoke all. |
| Brute force / credential stuffing | Redis rate limit (e.g. 5 login attempts/min/IP), lockout after 5 failures, optional MFA. |
| User enumeration | Same response for "email exists"/"doesn't exist" on register, login, forgot-password. |
| Privilege escalation | Permission checked on **every** route via dependency; ownership checked in services; role cannot be set at registration. |
| Malicious upload | Allow-list + magic-byte check, 25 MB limit enforced while streaming, random stored names, files never executed or served with their original Content-Type unless safe; `Content-Disposition: attachment` for downloads; previews only for PDF/images/TXT/CSV, text always sent as `text/plain`, with `Content-Security-Policy: sandbox`; `X-Content-Type-Options: nosniff`. |
| Path traversal | Storage keys are server-generated UUIDs; user input never becomes a path. |
| CSRF (OAuth) | Random `state` stored in Redis, single use. |
| Secrets in code | `.env` (gitignored) loaded by pydantic-settings; `.env.example` documents keys. |
| Tampering / snooping on disk **(M2)** | Chunked AES-256-GCM with a per-file key; keys wrapped by versioned master keys (envelope encryption); the private bucket holds only ciphertext – see [§8](#8-milestone-2--encryption-storage-and-sharing) and [key-management.md](key-management.md). |

## 6. Deployment view (M1 – local)

```mermaid
flowchart TB
    subgraph host["Developer laptop – docker compose"]
        FE["frontend<br/>node:20 · Vite dev server :5173"]
        BE["backend<br/>python:3.12-slim · Uvicorn :8000"]
        PG[("postgres:16<br/>:5432 · volume pgdata")]
        MO[("mongo:7<br/>:27017 · volume mongodata")]
        RE[("redis:7<br/>:6379")]
        VOL[["./storage volume"]]
    end
    FE --> BE
    BE --> PG
    BE --> MO
    BE --> RE
    BE --> VOL
```

All services have health checks; the backend waits for the databases to be healthy before starting. **(M4)** moves this to a cloud VM / AWS with NGINX + HTTPS.

## 7. Mapping to the brief's reference architecture

| Brief component | TrustShare implementation |
|---|---|
| Web App (React/Next.js) | React + Vite SPA |
| Admin Dashboard | Admin pages in the same SPA, gated by permissions |
| API Gateway: SSL, Auth, Validation, Rate limiting, Audit logging, Routing | FastAPI middleware + dependencies (NGINX/TLS added in M4) |
| Auth Service | `AuthService`, `MfaService`, `OAuthService` |
| File Service | `FileService`, `FolderService`, `StorageBackend` |
| Encryption Service | **M2** – `EncryptionService` + `Keyring` (chunked AES-256-GCM, envelope keys, rotation), `S3Storage` |
| Sharing Service | **M2** – `ShareService`: link + direct shares in PostgreSQL (hashed tokens, permission, expiry, revocation, limits) |
| Notification Service | Email (M1: verification/reset) → **M3** in-app + email alerts |
| Analytics Service | **M3** – aggregations over MongoDB activity logs |
| Data layer: PostgreSQL, MongoDB, Redis, encrypted storage, audit logs | As in §1 (audit logs = MongoDB `activity_logs`) |
| Infrastructure: Docker, CI/CD (GitHub Actions), AWS | Docker Compose + GitHub Actions now; cloud in M4 |
| Message queue, Kubernetes, SIEM/IDS, ML anomaly detection, mobile/desktop clients, FCM, Captcha | **Future scope** (see requirements §8) |

---

## 8. Milestone 2 – Encryption, storage and sharing

Requirements: Milestone 2 brief (AES-256 encryption, cloud storage, encrypted retrieval, secure sharing,
access permissions, link expiry, key management, secure decryption) plus the mentor's dashboards
(user File Analytics, admin Security Dashboard, user Security page). Key details:
[key-management.md](key-management.md).

### 8.1 Components added

| Component | Responsibility |
|---|---|
| `EncryptionService` | Chunked AES-256-GCM encrypt/decrypt of file streams; generates one DEK per file. |
| `Keyring` | Versioned master keys (KEKs) from the environment; wraps/unwraps DEKs. The only code that sees KEKs. |
| `S3Storage` (`StorageBackend`) | Upload/download/delete objects in a **private** bucket via the S3 API (boto3). RustFS locally, AWS S3 in the cloud. |
| `ShareService` | Link shares (hashed token) and direct shares (registered recipient); permission, expiry, revocation, download limit. |
| `AnalyticsService` | Date-range aggregations over activity logs and file metadata (user File Analytics, admin dashboards). |
| `SecurityEventService` | Records security events with severity (failed/locked logins, unauthorized and blocked requests, tampering, suspicious downloads). |

### 8.2 Encrypted upload

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
    API->>API: Permission file:upload, type allow-list, size, quota, magic bytes, SHA-256 (as in M1)
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

### 8.3 Encrypted download / preview

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

### 8.4 Share links and direct sharing

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

### 8.5 Key rotation

Admin adds master key `v(n+1)` → sets it active → runs `rotate_keys` → every `file_keys` row on an older
version is unwrapped and re-wrapped with the new key (batches, idempotent) → old KEK removed when unused.
Files are never re-encrypted; downloads keep working during rotation.

### 8.6 Dashboards (mentor's additions)

- **User:** new sidebar (Dashboard, My Files, Shared with Me, Shared by Me, Recent, Favorites, Trash,
  Storage, File Analytics, Activity Logs, Security, Settings); File Analytics with summary cards, storage by
  type, uploads/downloads/sharing over time, recent uploads/downloads and a date range; a Security page
  describing the active protections.
- **Admin:** separate admin panel with a **Security Dashboard** – login metrics and charts, unauthorized
  and blocked attempts, security events by severity and type, recent logins with IP and location, audit
  log. Every admin endpoint requires the `audit:read` / `user:read` permissions on the **backend**; the
  hidden menu is only a convenience.

### 8.7 API surface added in Milestone 2 (planned)

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| POST | `/files/{id}/shares` | `share:create` + owner | Create a link or direct share |
| GET | `/files/{id}/shares` | owner | List a file's shares with status |
| GET | `/shares/sent` · `/shares/received` | logged in | "Shared by Me" / "Shared with Me" |
| DELETE | `/shares/{share_id}` | owner | Revoke |
| GET | `/shares/{share_id}/preview` · `/shares/{share_id}/download` | recipient | Open a file shared with me |
| GET | `/s/{token}` · `/s/{token}/preview` · `/s/{token}/download` | public (token) | Link visitor access |
| POST/DELETE | `/files/{id}/favorite` | owner / recipient | Favorites |
| GET | `/analytics/me?from&to` | logged in | User File Analytics |
| GET | `/admin/security/overview?from&to` | `audit:read` | Security Dashboard metrics and charts |
| GET | `/admin/security/logins` · `/events` · `/audit` | `audit:read` | Recent logins, security events, audit log |

### 8.8 Deployment view (Milestone 2 – local)

`docker compose` gains a **`rustfs`** service (RustFS – open-source S3-compatible object storage, private bucket
created on start, console on :9001/rustfs/console/). Leaving `S3_ENDPOINT_URL` empty and putting real AWS credentials in `.env`
switches the same code to **AWS S3**. HTTPS locally is provided by a Caddy reverse proxy with a trusted
local certificate (Phase 9).
