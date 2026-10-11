# TrustShare: Secure File-Sharing System

A secure file-sharing and document management platform. Files are encrypted server-side with a unique **AES-256** key per file before being stored in cloud storage, and shared through permission-controlled, expiring links.

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Next.js](https://img.shields.io/badge/frontend-Next.js-black)

## Features

- **Authentication:** registration, login, MFA, password recovery, JWT sessions, OAuth2
- **Access control:** role-based access control (RBAC)
- **File management:** secure upload, folders, categories, search and filters, versioning, metadata
- **Secure sharing:** shareable links, permissions, expiring access, download restrictions
- **Encryption:** server-side AES-256, per-file keys, key rotation, HTTPS/TLS
- **Monitoring:** download tracking, access history, audit logs, suspicious activity detection
- **Notifications:** share alerts, security warnings, email notifications, expiration reminders
- **Analytics:** storage usage, upload/download reports, security and admin dashboards

## Architecture

```
Next.js Frontend ──HTTPS──> FastAPI Backend ──> AES-256 Encryption
                                 │                    │
                 ┌───────────────┼──────────────┐     └──> AWS S3 / Azure Blob (encrypted files only)
                 ▼               ▼              ▼
            PostgreSQL        MongoDB         Redis
        (users, metadata,  (activity &     (cache, sessions,
          permissions)      audit logs)       tokens)
```

**Encryption workflow**

1. User uploads a file over HTTPS.
2. Backend validates file type, size, and permissions.
3. A unique AES-256 key is generated for the file.
4. The file is encrypted on the server.
5. The encrypted file is stored in S3 / Azure Blob.
6. Metadata and permissions go to PostgreSQL; activity logs go to MongoDB.
7. Authorized users access the file via a secure share link.
8. The backend decrypts the file temporarily in memory and delivers it.

## Tech Stack

| Layer | Technologies |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, Alembic, Uvicorn, `cryptography` |
| Frontend | React.js, Next.js, Tailwind CSS, Axios |
| Databases | PostgreSQL, MongoDB, Redis |
| Security | JWT, OAuth2, AES-256, bcrypt, HTTPS/TLS |
| Storage & Deployment | AWS S3 / Azure Blob, Docker, Docker Compose, AWS / Azure |

## Project Structure

```
trustshare/
├── backend/            # FastAPI application
├── frontend/           # Next.js application
├── docs/               # Documentation and diagrams
├── docker-compose.yml
├── .env.example
├── SECURITY.md
└── LICENSE
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose

### Installation

```bash
git clone https://github.com/Vimaladharsan/trustshare.git
cd trustshare
cp .env.example .env    # fill in your own values
```

### Run with Docker

```bash
docker compose up --build
```

### Run locally

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Environment Variables

See `.env.example`. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `MONGO_URL` | MongoDB connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET` | JWT signing secret |
| `MASTER_KEY` | Master key protecting per-file encryption keys |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 credentials |
| `S3_BUCKET` | Encrypted file storage bucket |

> **Never commit `.env` files or encryption keys.**

## Roadmap

- [ ] **Milestone 1:** Project setup, authentication, RBAC, secure upload, file dashboard
- [ ] **Milestone 2:** AES-256 encryption, cloud storage, secure sharing, expiring links, key management
- [ ] **Milestone 3:** Monitoring, audit logs, notifications, analytics, suspicious activity detection
- [ ] **Milestone 4:** Security testing, Docker/cloud deployment, documentation, demo

## Security

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

## Author

**Vimal**: [GitHub](https://github.com/Vimaladharsan)
