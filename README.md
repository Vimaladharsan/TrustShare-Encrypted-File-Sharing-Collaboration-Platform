# TrustShare: Secure File-Sharing System

A secure file-sharing and document management platform – a private alternative to Google Drive. Users upload files that are validated and stored safely, organise them in folders, and (from Milestone 2) share them through permission-controlled, expiring links, with every file encrypted server-side using a unique **AES-256-GCM** key.

![CI](https://github.com/Vimaladharsan/TrustShare-Encrypted-File-Sharing-Collaboration-Platform/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![React](https://img.shields.io/badge/frontend-React_%2B_Vite-61DAFB)
![Status](https://img.shields.io/badge/milestone_1-complete-2ea44f)

## Status

TrustShare is built milestone by milestone. **Milestone 1 (foundation) is complete**; Milestone 2 (encryption and sharing) is next.

## Features

### Authentication and sessions
- Registration with password-strength rules (checked live in the UI and enforced on the server); passwords hashed with **bcrypt**; the same answer for new and already-registered emails (the owner gets a notice email), so sign-up can't reveal who has an account
- **JWT access tokens** (15 min, kept in memory only) and **rotating refresh tokens** (7 days, HttpOnly cookie, stored hashed in Redis) with reuse detection
- Logout, and **log out of all devices** from Settings
- **Change password** in Settings (confirms the current one; other devices are logged out)
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

### Platform
- **Activity log** in MongoDB for every important action, including **login history** (successful logins with method, failed logins with reason, lockouts) and rejected uploads (who, what, IP, user agent, request ID)
- Health endpoint that checks PostgreSQL, MongoDB and Redis
- Standard JSON error format with request IDs, security headers, structured logging
- Everything runs with Docker Compose; database migrations run automatically on start

## Architecture

```
React + Vite ──HTTPS──> FastAPI backend ──> StorageBackend (local now → AES-256-GCM on S3 in M2)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         PostgreSQL        MongoDB          Redis
       (users, roles,   (file metadata,  (sessions, refresh
        permissions)     folders, logs)   tokens, rate limits)
```

Each database is used for what it is good at: PostgreSQL for consistent relational data, MongoDB for flexible, high-volume documents, Redis for fast data that expires on its own. The backend is layered – **routes → services → repositories** – so HTTP handling, business rules and data access stay separate.

Full design with diagrams: [docs/architecture.md](docs/architecture.md) · data model: [docs/database.md](docs/database.md) · requirements and permission matrix: [docs/requirements.md](docs/requirements.md) · wireframes: [docs/wireframes.html](docs/wireframes.html).

**Planned encryption workflow (Milestone 2)**

1. User uploads a file over HTTPS.
2. Backend validates type, size, content and permissions.
3. A unique AES-256 key is generated for the file and wrapped by a master key (envelope encryption).
4. The file is encrypted on the server and stored in S3.
5. Metadata and activity logs are recorded.
6. Authorized users access the file through a secure, expiring share link.
7. The backend decrypts the file in memory only and delivers it.

## Tech Stack

| Layer | Technologies |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2, Alembic, Uvicorn |
| Frontend | React 19, Vite, React Router, Tailwind CSS, Axios, lucide-react, sonner |
| Databases | PostgreSQL 16, MongoDB 7, Redis 7 |
| Security | bcrypt, JWT, TOTP (pyotp), Fernet, permission-based RBAC (AES-256-GCM in M2) |
| Quality | pytest (69 tests), ruff, ESLint, Prettier, pre-commit, GitHub Actions |
| Deployment | Docker, Docker Compose |

## Project Structure

```
TrustShare/
├── backend/
│   ├── app/
│   │   ├── api/            # Routes (/auth, /users, /admin, /files, /folders, /trash, /health)
│   │   ├── core/           # Config, security, permissions, errors, logging, middleware
│   │   ├── db/             # PostgreSQL, MongoDB and Redis connections
│   │   ├── models/         # SQLAlchemy models
│   │   ├── repositories/   # Data access
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── scripts/        # create_admin, seed_demo
│   │   ├── services/       # Business logic (auth, MFA, upload validation, folders, trash)
│   │   └── storage/        # StorageBackend implementations (local; S3 in M2)
│   ├── alembic/            # Database migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/            # Axios client with automatic token refresh
│       ├── auth/           # Auth context and hooks
│       ├── components/     # Layout, file table, dialogs, upload modal
│       ├── pages/          # Login, register, files, trash
│       └── utils/
├── docs/                   # Architecture, database design, requirements, wireframes
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

- Frontend: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

Migrations run automatically when the backend container starts.

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

Optional settings with defaults include `MAX_UPLOAD_MB` (25), `DEFAULT_QUOTA_MB` (1024), `ACCESS_TOKEN_TTL_MINUTES` (15), `REFRESH_TOKEN_TTL_DAYS` (7), `MAX_FAILED_LOGINS` (5) and `LOCKOUT_MINUTES` (15).

> **Never commit `.env` files or secrets.**

## API

Interactive documentation is available at `/docs` while the backend is running.

| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Auth | `POST /api/auth/register`, `/login`, `/mfa/verify`, `/refresh`, `/logout`, `/logout-all`, `/forgot-password`, `/reset-password`, `/verify-email`, `/verify-email/resend`; `GET /api/auth/providers`, `/google/login`, `/google/callback` |
| Profile & MFA | `GET /api/users/me`, `POST /api/users/me/password`, `GET /api/users/me/mfa`, `POST /api/users/me/mfa/setup`, `/enable`, `/disable` |
| Admin | `GET /api/admin/users` (requires `user:read`), `PATCH /api/admin/users/{id}` (role, enable/disable), `POST /api/admin/users/{id}/unlock` (require `user:manage`), `DELETE /api/admin/users/{id}` (inactive 30+ days, requires `user:delete_inactive`) |
| Files | `POST /api/files` (upload), `GET /api/files`, `GET /api/files/usage`, `GET/PATCH/DELETE /api/files/{id}`, `GET /api/files/{id}/download`, `GET /api/files/{id}/preview`, `POST /api/files/{id}/trash`, `/restore` |
| Folders | `GET/POST /api/folders`, `GET/PATCH/DELETE /api/folders/{id}`, `POST /api/folders/{id}/trash`, `/restore` |
| Trash | `POST /api/trash/restore`, `/delete`, `/restore-all`, `/empty` |
| Sharing (M2) | `POST/GET /api/files/{id}/shares` (create link or direct share / list), `GET /api/shares/sent`, `GET /api/shares/received`, `DELETE /api/shares/{id}` (revoke), `GET /api/shares/{id}/preview` · `/download` (recipient) |
| Public links (M2) | `GET /api/s/{token}` · `/preview` · `/download` – no login, rate-limited per IP |

## Roadmap

- [x] **Milestone 1:** design, Docker setup, authentication, RBAC, MFA, secure upload, file dashboard, CI
- [ ] **Milestone 2:** AES-256-GCM encryption, cloud storage, secure sharing, expiring links, key management
- [ ] **Milestone 3:** monitoring, audit logs, notifications, analytics, suspicious-activity detection
- [ ] **Milestone 4:** security testing, cloud deployment, documentation, demo

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

## Author

**S Vimaladharsan**: [GitHub](https://github.com/Vimaladharsan)
