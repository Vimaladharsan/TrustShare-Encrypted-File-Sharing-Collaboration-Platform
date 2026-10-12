# TrustShare: Secure File-Sharing System

A secure file-sharing and document management platform. Files will be encrypted server-side with a unique **AES-256-GCM** key per file before storage, and shared through permission-controlled, expiring links.

![CI](https://github.com/Vimaladharsan/TrustShare-Encrypted-File-Sharing-Collaboration-Platform/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![React](https://img.shields.io/badge/frontend-React_%2B_Vite-61DAFB)
![Status](https://img.shields.io/badge/status-in_development-f7c948)

## Status

TrustShare is being built milestone by milestone. **Milestone 1 (foundation) is in progress.**

**Working today**

- FastAPI backend connected to **PostgreSQL**, **MongoDB** and **Redis**, with a combined `/api/health` check
- SQLAlchemy models and **Alembic migrations**, with roles and permissions seeded by the first migration
- **Registration and JWT login** with bcrypt password hashing
- **Permission-based access control**: routes check permissions (`file:upload`, `user:read`, …), not role names, so new roles need no code changes
- Admin-only user listing with search and pagination
- Standard error format, request logging and request IDs
- React + Vite + Tailwind frontend with a live system-status page
- Tests with pytest, linting with ruff, ESLint and Prettier, pre-commit hooks and a **GitHub Actions CI** pipeline that runs against real databases

**Planned**: see the [Roadmap](#roadmap).

## Features (target)

- **Authentication:** registration, login, MFA, password recovery, JWT sessions, Google OAuth
- **Access control:** role-based access control with admin, user and guest roles
- **File management:** secure upload, folders, search and filters, versioning, metadata
- **Secure sharing:** shareable links, permissions, expiring access, download restrictions
- **Encryption:** server-side AES-256-GCM, per-file keys, key rotation, HTTPS/TLS
- **Monitoring:** download tracking, access history, audit logs, suspicious-activity detection
- **Notifications:** share alerts, security warnings, email notifications, expiration reminders
- **Analytics:** storage usage, upload/download reports, security and admin dashboards

## Architecture

```
React + Vite ──HTTPS──> FastAPI backend ──> StorageBackend (local now → AES-256-GCM on S3 later)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         PostgreSQL        MongoDB          Redis
       (users, roles,   (files, folders, (sessions, one-time
        permissions)     activity logs)   tokens, rate limits)
```

Each database is used for what it is good at. The full design, with Mermaid diagrams, is in [docs/architecture.md](docs/architecture.md); the data model is in [docs/database.md](docs/database.md).

**Planned encryption workflow**

1. User uploads a file over HTTPS.
2. Backend validates file type, size and permissions.
3. A unique AES-256 key is generated for the file.
4. The file is encrypted on the server.
5. The encrypted file is stored in the file store.
6. Metadata and activity logs are recorded.
7. Authorized users access the file through a secure share link.
8. The backend decrypts the file temporarily in memory and delivers it.

## Tech Stack

| Layer | Technologies |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy (async), Pydantic, Alembic, Uvicorn |
| Frontend | React 19, Vite, React Router, Tailwind CSS, Axios |
| Databases | PostgreSQL 16, MongoDB 7, Redis 7 |
| Security | JWT, bcrypt, permission-based RBAC (AES-256-GCM planned) |
| Quality | pytest, ruff, ESLint, Prettier, pre-commit, GitHub Actions |
| Deployment | Docker, Docker Compose |

## Project Structure

```
TrustShare/
├── backend/
│   ├── app/
│   │   ├── api/            # Routers (/auth, /users, /admin, /health) and dependencies
│   │   ├── core/           # Config, security, permissions, errors, logging, middleware
│   │   ├── db/             # PostgreSQL, MongoDB and Redis connections
│   │   ├── models/         # SQLAlchemy models
│   │   ├── repositories/   # Data access
│   │   ├── schemas/        # Pydantic request/response models
│   │   └── services/       # Business logic
│   ├── alembic/            # Database migrations
│   └── tests/
├── frontend/               # React + Vite + Tailwind app
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
cp .env.example .env    # then change every "change-me" value
docker compose up --build
```

- Frontend: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs

Migrations run automatically when the backend container starts.

### Run tests and linters

```bash
cd backend
pip install -r requirements-dev.txt
pytest
ruff check .
```

## Environment Variables

See [.env.example](.env.example).

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | PostgreSQL credentials |
| `MONGO_USER` / `MONGO_PASSWORD` | MongoDB credentials |
| `REDIS_PASSWORD` | Redis password |
| `JWT_SECRET` | JWT signing secret (at least 32 characters) |

> **Never commit `.env` files or secrets.**

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Status of PostgreSQL, MongoDB and Redis |
| `POST` | `/api/auth/register` | Create an account (role: user) |
| `POST` | `/api/auth/login` | Log in and receive an access token |
| `GET` | `/api/users/me` | The logged-in user's profile |
| `GET` | `/api/admin/users` | List users with search and pagination (requires `user:read`) |

Interactive documentation is available at `/docs` while the backend is running.

## Roadmap

- [ ] **Milestone 1:** project setup ✅, authentication ✅, RBAC ✅, CI ✅, secure upload, file dashboard
- [ ] **Milestone 2:** AES-256-GCM encryption, cloud storage, secure sharing, expiring links, key management
- [ ] **Milestone 3:** monitoring, audit logs, notifications, analytics, suspicious-activity detection
- [ ] **Milestone 4:** security testing, cloud deployment, documentation, demo

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

## Author

**S Vimaladharsan**: [GitHub](https://github.com/Vimaladharsan)
