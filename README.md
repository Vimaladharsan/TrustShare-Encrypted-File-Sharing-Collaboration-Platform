# TrustShare: Secure File-Sharing System

A secure file-sharing and document management platform – a private alternative to Google Drive. Every file is validated, **encrypted server-side with its own AES-256-GCM key** (envelope encryption with rotatable master keys) and stored in private cloud object storage (S3 API or Azure Blob Storage). Users organise files in folders and share them through **permission-controlled, expiring, revocable links** or directly with other users – with analytics for users and a security dashboard for admins.

![CI](https://github.com/Vimaladharsan/TrustShare-Encrypted-File-Sharing-Collaboration-Platform/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![React](https://img.shields.io/badge/frontend-React_%2B_Vite-61DAFB)
![Status](https://img.shields.io/badge/milestone_2-complete-2ea44f)

## Status

TrustShare is built milestone by milestone. **Milestone 1** (foundation: auth, RBAC, MFA, upload, dashboard) and **Milestone 2** (encryption, cloud storage, secure sharing, key management, dashboards, HTTPS) are complete.

## Features

### Authentication and sessions
- Registration with password-strength rules (checked live in the UI and enforced on the server); passwords hashed with **bcrypt**; the same answer for new and already-registered emails (the owner gets a notice email), so sign-up can't reveal who has an account
- **JWT access tokens** (15 min, kept in memory only) and **rotating refresh tokens** (7 days, HttpOnly cookie, stored hashed in Redis) with reuse detection (a 10-second grace window lets the same browser retry a just-rotated token – two tabs or fast reloads – without being logged out)
- Logout, and **log out of all devices** from Settings
- **Change password** in Settings (confirms the current one; other devices are logged out)
- **My account** page with Profile · Security · Devices · Account tabs: edit your display name; see every signed-in **device** (browser, OS, IP, approximate location, last active) and **sign out one device** – its access token stops working at once, not after 15 minutes; generate **new backup codes** (needs a current code, old codes stop working)
- **Delete my account**: confirmed with password (or typed email for Google-only accounts) plus a 2-step code if on; erases every file, object, wrapped key, share link, folder and session, keeps the audit trail, emails a confirmation; the last admin can't delete themselves
- **Google login** (OAuth 2.0 Authorization Code flow with PKCE): ID token verified against Google's keys; links to an existing account with the same verified email, otherwise creates a User; MFA still required if enabled
- **Email verification**: a single-use link (24 h) is emailed on sign-up; unverified users see a reminder with a Resend button (or are blocked from logging in with `REQUIRE_EMAIL_VERIFICATION=true`)
- **Forgot password**: emailed single-use reset link (15 min, stored only as a hash); resetting logs out every device
- **Two-step verification (TOTP)** with QR-code setup for Google Authenticator and one-time backup codes
- Account lockout after 5 failed logins (15 min) and per-IP rate limiting on login and registration

### Roles and permissions
- **Admin**, **User** and **Guest** roles built from permissions such as `file:upload` or `user:read` – routes check permissions, not role names, so new roles need no code changes
- Guests are read-only; Admins create the first Admin from the command line, then manage users in the **Users** page: change roles, disable/enable accounts (disabled users are logged out everywhere), unlock lockouts – but never their own account or the last admin. Admins **can't open other users' files**; they can delete accounts that haven't logged in for 30+ days, with all their files
- Ownership checks on every file and folder (other users' items return 404)

### Secure upload
- Allow-list of types: PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG
- **Content check** – magic bytes, plus the internal structure of Office files – so a renamed `.exe` is rejected
- 25 MB limit enforced while streaming, per-user storage quota, **SHA-256** fingerprint with duplicate detection
- Files stored under random names (the user's filename never becomes a path); metadata in MongoDB
- Upload dialog with drag and drop, several files at once, per-file progress, cancel/retry and clear error messages

### File dashboard
- Drive-like layout: sidebar, search across all folders, storage meter, account menu
- Nested folders with breadcrumbs; create, rename and move files and folders
- Category filters, sortable file table, download, and **in-app preview** of PDFs, images and text files (served in a sandbox)
- Trash with restore, bulk restore/delete, empty trash and permanent delete
- Loading, empty and error states; responsive layout
- Buttons adapt to the user's permissions (enforced by the backend regardless)

### Encryption and storage (Milestone 2)
- **AES-256-GCM** with a fresh random 256-bit key per file, in 1 MiB authenticated chunks (format "TSE1"): any changed, missing, reordered or swapped chunk is detected and the download is refused
- **Envelope encryption:** each file key is stored only wrapped by a versioned **master key** (`MASTER_KEYS`); keys never appear in responses, logs or the browser (tests check this)
- Encrypted bytes in private **object storage** – RustFS locally, **Azure Blob Storage** or **AWS S3** by configuration (`STORAGE_PROVIDER`) – metadata in MongoDB, wrapped keys in PostgreSQL – no single store reveals a file
- **Key rotation** without re-encrypting files (`python -m app.scripts.rotate_keys`), crypto-shredding on permanent delete, migration of Milestone 1 plaintext files
- Decryption only in memory, after authorization; integrity failures return a safe error – details: [docs/key-management.md](docs/key-management.md)

### Secure sharing (Milestone 2)
- **Share links** for anyone (no account): view-only or view & download, expiry as a preset (1 hour … 30 days) or an exact date and time (max 30 days), optional download limit, instant revoke; 256-bit tokens stored only as SHA-256 hashes and hidden in logs
- **Direct sharing** with registered users ("Shared with me" / "Shared by me"); the recipient gets an email notice
- Every access re-checks revocation, expiry, limit, file status and the owner's account and permissions – trashing a file or disabling its owner stops all links at once

### Dashboards (Milestone 2)
- **User:** Dashboard, Recent, Favorites, Storage breakdown, **File Analytics** (storage by type, uploads, downloads incl. unique users and shared downloads, sharing trends, date range, change vs previous period), own Activity Logs, and a Security page
- **Admin panel:** **Security Dashboard** (logins, failed logins, unauthorized and blocked attempts, security events by severity, recent logins with IP and location), audit log viewer with **CSV export** (formula-injection safe, the export itself is audited), storage per account (sizes only – admins can't open users' files), sharing reports, system monitoring
- **Security events** recorded automatically: repeated failed logins, lockouts, suspicious IPs, new-IP sign-ins, token reuse, 403s and forged tokens, rate-limit blocks, disguised or tampered files, download anomalies, admin actions

### Platform
- **HTTPS** through a Caddy reverse proxy (TLS 1.3) at https://localhost:8443; real client IPs via trusted proxy headers
- **Activity log** in MongoDB for every important action, including **login history** (successful logins with method, failed logins with reason, lockouts) and rejected uploads (who, what, IP, user agent, request ID)
- Health endpoint that checks PostgreSQL, MongoDB, Redis and object storage
- Standard JSON error format with request IDs, security headers, structured logging
- Everything runs with Docker Compose; database migrations run automatically on start

## Architecture

```
Browser ──HTTPS──> Caddy ──> React + Vite (UI)
                     └─/api─> FastAPI backend ──encrypt / decrypt (AES-256-GCM)──> Object storage
                                    │                                           (RustFS / AWS S3,
              ┌─────────────────────┼─────────────────────┐                     ciphertext only)
              ▼                     ▼                     ▼
         PostgreSQL              MongoDB                Redis
   (users, roles, wrapped     (file metadata,      (sessions, refresh
    file keys, shares)       activity logs,         tokens, rate limits)
                             security events)
```

Each database is used for what it is good at: PostgreSQL for consistent relational data, MongoDB for flexible, high-volume documents, Redis for fast data that expires on its own. The backend is layered – **routes → services → repositories** – so HTTP handling, business rules and data access stay separate.

Full design with diagrams: [docs/architecture.md](docs/architecture.md) · data model: [docs/database.md](docs/database.md) · requirements and permission matrix: [docs/requirements.md](docs/requirements.md) · wireframes: [docs/wireframes.html](docs/wireframes.html).

**Encryption workflow (implemented in Milestone 2)**

1. The user uploads a file over HTTPS.
2. The backend validates type, size, content and permissions.
3. A unique AES-256 key is generated for the file and wrapped by the active master key (envelope encryption).
4. The file is encrypted in authenticated chunks and stored in object storage under a random name.
5. Metadata (MongoDB), the wrapped key (PostgreSQL) and an activity log entry are recorded.
6. The owner, a direct-share recipient or a valid share link may access the file – checked on every request.
7. The backend unwraps the key, verifies and decrypts the file in memory only, and streams it.

## Tech Stack

| Layer | Technologies |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2, Alembic, Uvicorn |
| Frontend | React 19, Vite, React Router, Tailwind CSS, Axios, Recharts, lucide-react, sonner |
| Data & storage | PostgreSQL 16, MongoDB 7, Redis 7, object storage: Azure Blob Storage (azure-storage-blob) or S3 API via boto3 (RustFS locally / AWS S3) |
| Security | AES-256-GCM (`cryptography`), envelope encryption with versioned master keys, bcrypt, JWT, TOTP (pyotp), Fernet, permission-based RBAC, Caddy (TLS) |
| Quality | pytest (204 tests), Postman/Newman collection, ruff, ESLint, Prettier, pre-commit, GitHub Actions |
| Deployment | Docker, Docker Compose (7 services incl. RustFS and Caddy) |

## Project Structure

```
TrustShare/
├── backend/
│   ├── app/
│   │   ├── api/            # Routes (auth, users, admin, files, folders, trash, shares, analytics, health)
│   │   ├── core/           # Config, security, permissions, errors, logging, middleware
│   │   ├── crypto/         # Master-key keyring (wraps and unwraps file keys)
│   │   ├── db/             # PostgreSQL, MongoDB and Redis connections
│   │   ├── models/         # SQLAlchemy models
│   │   ├── repositories/   # Data access
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── scripts/        # create_admin, seed_demo, encrypt_existing_files, rotate_keys, copy_objects, remove_test_accounts
│   │   ├── services/       # Business logic (auth, MFA, upload, encryption, sharing, analytics, security events)
│   │   └── storage/        # S3 + Azure Blob adapters, SecureFileStore (encrypt on write, verify + decrypt on read)
│   ├── alembic/            # Database migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/            # Axios client with automatic token refresh
│       ├── auth/           # Auth context and hooks
│       ├── components/     # Layouts, file table, dialogs, upload, share dialog, charts
│       ├── pages/          # Auth, files, sharing, analytics, security, admin panel
│       └── utils/
├── caddy/                  # Caddyfile for local HTTPS
├── docs/                   # Architecture, database design, key management, requirements, wireframes
├── postman/                # Postman collection + environment (Milestone 2 API checks)
├── .github/workflows/      # CI pipeline
├── docker-compose.yml
└── .env.example
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- For running outside Docker: Python 3.12+ and Node.js 20+

### Run with Docker

```bash
git clone https://github.com/Vimaladharsan/TrustShare-Encrypted-File-Sharing-Collaboration-Platform.git
cd TrustShare-Encrypted-File-Sharing-Collaboration-Platform
cp .env.example .env    # then replace every "change-me" value
docker compose up -d --build
```

- **App over HTTPS: https://localhost:8443** (Caddy reverse proxy, TLS 1.3)
- Frontend (plain HTTP, development): http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health
- Object storage console (RustFS): http://localhost:9001/rustfs/console/

Migrations run automatically when the backend container starts.

### HTTPS (local)

The `caddy` service terminates TLS with certificates from its own local certificate authority and
forwards `/api/*` to FastAPI and everything else to the React app. The backend reads the visitor's
real IP from `X-Forwarded-For`, but only from proxies inside the Docker network.

Browsers warn until they trust Caddy's root certificate. To trust it for your Windows user only:

```powershell
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ..\caddy-root.crt
Import-Certificate -FilePath ..\caddy-root.crt -CertStoreLocation Cert:\CurrentUser\Root
```

(Or double-click the file → Install Certificate → Current User → "Trusted Root Certification
Authorities".) The certificate stays valid across restarts because Caddy keeps it in the
`caddydata` volume. To make emailed links and share links use HTTPS too, set
`FRONTEND_URL=https://localhost:8443` in `.env`.

### Using real AWS S3 instead of RustFS

The code speaks the plain S3 API, so switching is configuration only:

1. AWS console → **S3** → create a bucket (e.g. in `ap-south-1`), keep **Block all public access**
   on, default encryption SSE-S3 on (an extra layer – the objects are already AES-256-GCM encrypted).
2. **IAM** → create a user for the app (no console access) with the least-privilege policy in
   [docs/aws-iam-policy.json](docs/aws-iam-policy.json) (replace `YOUR-BUCKET-NAME`), then create an
   access key for it.
3. In `.env`: `S3_ENDPOINT_URL=` (empty), `S3_REGION=ap-south-1`, `S3_BUCKET=<bucket>`,
   `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` = the new key → `docker compose up -d --force-recreate backend`.
4. Copy the existing encrypted objects across (no decryption needed – file keys stay valid):
   `docker compose exec backend python -m app.scripts.copy_objects --from-endpoint http://rustfs:9000`

Switching back = restore the RustFS values in `.env` and recreate the backend.

### Using Azure Blob Storage

The brief allows AWS S3 **or** Azure Blob Storage; TrustShare supports both (`STORAGE_PROVIDER`).
Azure for Students gives free credit without a credit card.

1. Azure portal → **Storage accounts → Create**: Standard performance, **LRS** redundancy (cheapest),
   region e.g. *Central India*. Under Advanced keep **Require secure transfer** on and
   **Allow enabling anonymous access on containers** off.
2. In the account → **Data storage → Containers → + Container** → name `trustshare-files`,
   access level **Private**.
3. **Security + networking → Access keys** → copy the **Connection string** (into `secrets.txt`).
4. In `.env`: `STORAGE_PROVIDER=azure`, `AZURE_STORAGE_CONNECTION_STRING=<connection string>`,
   `AZURE_CONTAINER=trustshare-files` → `docker compose up -d --force-recreate backend`.
5. Copy the existing encrypted objects from RustFS (no decryption – file keys stay valid):
   `docker compose exec backend python -m app.scripts.copy_objects --from-endpoint http://rustfs:9000`

The Azure code is tested against Azurite, Microsoft's Azure Storage emulator, on every CI run.
Switching back = `STORAGE_PROVIDER=s3` and recreate the backend.

### Create an admin and demo data

```bash
# First Admin (the password is asked for interactively)
docker compose exec backend python -m app.scripts.create_admin --email you@example.com --name "Admin"

# Optional demo data: a User and a Guest account, sample folders and files
docker compose exec backend python -m app.scripts.seed_demo
```

The seed script asks for one password used by both demo accounts (`user@example.com`, `guest@example.com`) and is safe to run more than once.

### Run tests and linters

```bash
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec frontend npm run lint
```

### Postman collection

`postman/TrustShare_M2.postman_collection.json` checks encrypted upload and download, access control,
share links (view vs download, limit, revoke, expiry), direct sharing, admin RBAC and analytics – 30
requests, run in order. Import it with `postman/TrustShare_local.postman_environment.json` into
Postman (Collection Runner), or run it with Newman in Docker:

```bash
docker run --rm --network trustshare_default -v "$PWD/postman:/etc/newman" postman/newman:6-alpine run TrustShare_M2.postman_collection.json -e TrustShare_local.postman_environment.json --env-var baseUrl=http://backend:8000/api
```

It creates two throwaway accounts (`@postman.example.com`); remove them afterwards with
`docker compose exec backend python -m app.scripts.remove_test_accounts postman.example.com`.

## Environment Variables

See [.env.example](.env.example).

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | PostgreSQL credentials |
| `MONGO_USER` / `MONGO_PASSWORD` | MongoDB credentials |
| `REDIS_PASSWORD` | Redis password |
| `JWT_SECRET` | Signs access tokens (at least 32 characters) |
| `MFA_ENCRYPTION_KEY` | Encrypts two-step verification secrets at rest |
| `SMTP_USER` / `SMTP_PASSWORD` | Optional Gmail account + app password for sending emails (otherwise emails go to the backend log) |
| `FRONTEND_URL` | Base URL used in email links (default `http://localhost:5173`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Optional Google login (button hidden when not set) |
| `REQUIRE_EMAIL_VERIFICATION` | `true` blocks login until the email is verified (default `false`: reminder only) |
| `MASTER_KEYS` / `ACTIVE_MASTER_KEY_VERSION` | Versioned 256-bit master keys (`1:<base64>,2:<base64>`) that wrap every file key, and the one used for new files – back them up separately; see [docs/key-management.md](docs/key-management.md) |
| `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_REGION` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Object storage for the encrypted files (empty endpoint = real AWS S3) |
| `RUSTFS_ACCESS_KEY` / `RUSTFS_SECRET_KEY` | Credentials of the local RustFS container |
| `STORAGE_PROVIDER` / `AZURE_STORAGE_CONNECTION_STRING` / `AZURE_CONTAINER` | `s3` (default) or `azure`; the Azure storage account's connection string and private container |

Optional settings with defaults include `MAX_UPLOAD_MB` (25), `DEFAULT_QUOTA_MB` (1024), `ACCESS_TOKEN_TTL_MINUTES` (15), `REFRESH_TOKEN_TTL_DAYS` (7), `MAX_FAILED_LOGINS` (5), `LOCKOUT_MINUTES` (15), `SHARE_LINK_MAX_DAYS` (30), `SHARE_LINK_RATE_LIMIT_PER_MINUTE` (60) and `INACTIVE_ACCOUNT_DAYS` (30).

> **Never commit `.env` files or secrets.**

## API

Interactive documentation is available at `/docs` while the backend is running.

| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Auth | `POST /api/auth/register`, `/login`, `/mfa/verify`, `/refresh`, `/logout`, `/logout-all`, `/forgot-password`, `/reset-password`, `/verify-email`, `/verify-email/resend`; `GET /api/auth/providers`, `/google/login`, `/google/callback` |
| Profile & MFA | `GET` · `PATCH` · `DELETE /api/users/me`, `POST /api/users/me/password`, `GET /api/users/me/sessions`, `DELETE /api/users/me/sessions/{id}`, `GET /api/users/me/mfa`, `POST /api/users/me/mfa/setup`, `/enable`, `/disable`, `/backup-codes` |
| Admin | `GET /api/admin/users` (requires `user:read`), `PATCH /api/admin/users/{id}` (role, enable/disable), `POST /api/admin/users/{id}/unlock` (require `user:manage`), `DELETE /api/admin/users/{id}` (inactive 30+ days, requires `user:delete_inactive`) |
| Files | `POST /api/files` (upload), `GET /api/files`, `GET /api/files/usage`, `GET/PATCH/DELETE /api/files/{id}`, `GET /api/files/{id}/download`, `GET /api/files/{id}/preview`, `POST /api/files/{id}/trash`, `/restore` |
| Folders | `GET/POST /api/folders`, `GET/PATCH/DELETE /api/folders/{id}`, `POST /api/folders/{id}/trash`, `/restore` |
| Trash | `POST /api/trash/restore`, `/delete`, `/restore-all`, `/empty` |
| Sharing (M2) | `POST/GET /api/files/{id}/shares` (create link or direct share / list), `GET /api/shares/sent`, `GET /api/shares/received`, `DELETE /api/shares/{id}` (revoke), `GET /api/shares/{id}/preview` · `/download` (recipient) |
| Analytics (M2) | `GET /api/analytics/me?from&to&tz`, `GET /api/files/storage`, `GET /api/files/recent`, `GET /api/files/favorites`, `PUT/DELETE /api/files/{id}/favorite`, `GET /api/activity/me` |
| Admin reports (M2) | `GET /api/admin/overview` (`user:read`), `GET /api/admin/security/overview`, `/security/logins`, `/security/events`, `GET /api/admin/audit`, `GET /api/admin/audit/export` (CSV) (`audit:read`) |
| Public links (M2) | `GET /api/s/{token}` · `/preview` · `/download` – no login, rate-limited per IP |

## Roadmap

- [x] **Milestone 1:** design, Docker setup, authentication, RBAC, MFA, secure upload, file dashboard, CI
- [x] **Milestone 2:** AES-256-GCM envelope encryption, S3-compatible storage, secure links and direct sharing, key rotation, user analytics, admin security dashboard, HTTPS
- [ ] **Milestone 3:** notifications, deeper monitoring and suspicious-activity detection (audit logs and analytics started in M2)
- [ ] **Milestone 4:** security testing, cloud deployment, documentation, demo

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

## Author

**S Vimaladharsan**: [GitHub](https://github.com/Vimaladharsan)
