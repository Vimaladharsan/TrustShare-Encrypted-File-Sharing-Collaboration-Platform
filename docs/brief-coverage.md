# TrustShare – Project Brief Coverage

This document maps every item of the project brief (*TrustShare: Secure File-Sharing System*) to
where it is implemented and how it is verified. It also lists, honestly, what was done differently
and what is out of scope.

**Legend:** ✅ implemented · 🔄 in progress (Milestone 4) · ➖ done differently (reason given) ·
⛔ out of scope (future work)

Paths are relative to the repository root. Backend tests are in `backend/tests/`; API checks are
in `postman/`.

---

## 1. Outcomes

| # | Brief outcome | Status | Where / evidence |
|---|---|---|---|
| i | Developed and deployed a secure file-sharing and document management platform | ✅ developed · 🔄 deployed | Runs with Docker Compose; cloud deployment is Milestone 4 |
| ii | Authentication and role-based access control | ✅ | [Module 1](#module-1--user-authentication), [permission matrix](requirements.md) |
| iii | Secure file upload and encrypted storage workflows | ✅ | [Module 2](#module-2--file-management), [Module 4](#module-4--encryption--security) |
| iv | Secure sharing and temporary access management | ✅ | [Module 3](#module-3--secure-sharing) |
| v | File activity monitoring and audit logging | ✅ | [Module 5](#module-5--access-monitoring) |
| vi | Notification and security alert systems | ✅ | [Module 6](#module-6--notifications) |
| vii | Analytics dashboards for storage usage and activity monitoring | ✅ | [Module 7](#module-7--analytics-dashboards) |
| viii | Server-side AES-256 encryption and secure key management | ✅ | [key-management.md](key-management.md) |
| ix | Deployed using Docker and AWS or Azure | ✅ Docker · ✅ Azure Blob Storage for files · 🔄 cloud hosting of the app | Milestone 4 |

---

## 2. Modules

### Module 1 – User Authentication

| Brief item | Status | Implementation | Verified by |
|---|---|---|---|
| Registration and login | ✅ | `app/api/routes/auth.py`, `app/services/auth_service.py` – bcrypt, password rules, lockout after 5 failures, per-IP rate limits | `test_auth.py` |
| Multi-factor authentication | ✅ | TOTP with QR code + one-time backup codes – `app/services/mfa_service.py` | `test_mfa.py` |
| Password recovery | ✅ | Emailed single-use reset link (15 min, stored hashed) – `password_reset_service.py` | `test_password_reset.py` |
| Session management | ✅ | Rotating refresh tokens in Redis with reuse detection, device list, sign out one device / all devices – `session_service.py`, `account_service.py` | `test_sessions.py`, `test_profile.py` |
| JWT authentication | ✅ | 15-minute access tokens, permission checks per route – `app/core/security.py`, `app/api/deps.py` | `test_auth.py`, `test_admin.py` |
| OAuth2 integration | ✅ | Google sign-in, Authorization Code flow with PKCE – `google_oauth_service.py` | `test_google_login.py` |
| *Extra* | ✅ | Email verification, new-device sign-in alert, account security score, delete my account | `test_email_verification.py`, `test_new_device_alert.py`, `test_account_overview.py`, `test_account.py` |

### Module 2 – File Management

| Brief item | Status | Implementation | Verified by |
|---|---|---|---|
| Secure file upload | ✅ | Type allow-list, magic-byte and Office-structure check, 25 MB streaming limit, quota, SHA-256 – `file_validation.py`, `file_service.py` | `test_files.py` |
| File categorization | ✅ | Category stored per file (document, spreadsheet, presentation, image, text); category filter chips | `test_files.py` |
| Folder management | ✅ | Nested folders, breadcrumbs, rename, move (incl. drag and drop), trash – `folder_service.py` | `test_folders.py`, `test_trash.py` |
| File search and filtering | ✅ | Name search across all folders, category filter, sorting – `GET /api/files?q=&category=` | `test_files.py` |
| File version management | ⛔ | Not built. Uploading the same file again is detected (SHA-256) and the user chooses *Keep both*; separate version history is future work | – |
| File metadata management | ✅ | Metadata in MongoDB (name, type, size, hash, folder, dates, favorites); rename, move, favorites, recent | `test_files.py`, `test_analytics.py` |
| *Extra* | ✅ | In-app preview, multi-select with ZIP download, trash with restore, password-protected vault | `test_bulk_files.py`, `test_vault.py` |

### Module 3 – Secure Sharing

| Brief item | Status | Implementation | Verified by |
|---|---|---|---|
| Shareable secure links | ✅ | 256-bit random tokens, only the SHA-256 hash stored, hidden in logs – `share_service.py` | `test_shares.py` |
| Permission management | ✅ | View-only or view & download; direct sharing with registered users | `test_shares.py` |
| Temporary access expiration | ✅ | Expiry preset or exact date (max 30 days), checked on every request; reminder before expiry | `test_shares.py`, `test_notifications.py` |
| Access-level configuration | ✅ | Edit a share without revoking it (permission, expiry, limit); optional link password | `test_share_edit.py`, `test_share_password_folder.py` |
| Download restrictions | ✅ | Optional download limit per link, enforced atomically | `test_shares.py` |
| Share activity monitoring | ✅ | Access history per share (opened, viewed, downloaded, refused + reason) | `test_share_access.py` |
| *Extra* | ✅ | Share several files or a whole folder at once, QR code for links | `test_bulk_share.py`, `test_share_password_folder.py` |

### Module 4 – Encryption & Security

**Encryption workflow** (brief steps i–x):

| Brief step | Status | How TrustShare does it |
|---|---|---|
| i. User uploads through the web app | ✅ | React upload dialog → `POST /api/files` over HTTPS |
| ii. Validate type, size and permissions | ✅ | `file_validation.py` + permission `file:upload` |
| iii. Generate a unique AES-256 key | ✅ | Fresh random 256-bit key per file |
| iv. Encrypt on the server | ✅ | AES-256-GCM in 1 MiB authenticated chunks – `encryption_service.py` |
| v. Store encrypted file in AWS S3 or Azure Blob | ✅ | Azure Blob Storage (in use) or S3 API – `app/storage/` |
| vi. Metadata and permissions in PostgreSQL | ➖ | Permissions, shares and wrapped keys are in **PostgreSQL**; file metadata is in **MongoDB**, as required by the Milestone 1 checklist. Bytes, metadata and keys live in three separate stores |
| vii. Activity logs in MongoDB | ✅ | `activity_logs` + hash-chained `audit_logs` |
| viii. Access through secure sharing links | ✅ | Every request re-checks revocation, expiry, limit, file and owner status |
| ix. Decrypt temporarily in memory | ✅ | Streamed chunk by chunk, never written to disk; GCM tag verified |
| x. Deliver securely to the authorized user | ✅ | HTTPS, `Cache-Control: no-store`, sandboxed preview |

**Security features:**

| Brief feature | Status | Implementation |
|---|---|---|
| AES-256 encryption | ✅ | AES-256-GCM, envelope encryption ([key-management.md](key-management.md)) |
| HTTPS/TLS | ✅ | Caddy reverse proxy, TLS 1.3 |
| JWT authentication | ✅ | Access + rotating refresh tokens |
| OAuth2 authentication | ✅ | Google sign-in with PKCE |
| Role-based access control | ✅ | Admin / User / Guest built from permissions |
| Temporary share links | ✅ | Expiring, revocable, limited links |
| Download tracking | ✅ | Every download logged; per-share counts and history |
| Audit logging | ✅ | Tamper-evident, hash-chained audit log with verification |
| Secure token generation | ✅ | `secrets` module, 256-bit tokens, stored only as hashes |
| Key rotation | ✅ | `python -m app.scripts.rotate_keys` re-wraps file keys – `test_key_rotation.py` |

**Key management:** unique key per file ✅ · keys managed on the server (versioned master keys
wrap file keys) ✅ · never exposed to users (tests check responses and logs) ✅ · periodic
rotation ✅ – `test_encryption.py`, `test_encrypted_storage.py`, `test_key_rotation.py`.

### Module 5 – Access Monitoring

| Brief item | Status | Implementation | Verified by |
|---|---|---|---|
| Download tracking | ✅ | `file.download` activity for owners, recipients and link visitors | `test_monitoring_audit.py` |
| File access history | ✅ | Per-file audit trail and per-share access history | `test_share_access.py` |
| Login activity monitoring | ✅ | Successful / failed logins with device and IP; admin login charts | `test_admin_security.py` |
| Audit logs | ✅ | `app/audit/` – append-only, SHA-256 hash chain, verify endpoint, CSV export | `test_monitoring_audit.py` |
| Security event monitoring | ✅ | Security events with severity and alert workflow – `app/security_monitoring/` | `test_admin_security.py` |
| Suspicious activity detection | ✅ | Rule engine with sliding windows in Redis (failed logins, unauthorized access, mass downloads, expired / revoked link abuse) | `test_detection.py`, `test_end_to_end_m3.py` |

### Module 6 – Notifications

| Brief item | Status | Implementation |
|---|---|---|
| File-sharing notifications | ✅ | In-app + email when a file or folder is shared with you |
| Access alerts | ✅ | Owner notified when a shared file is downloaded; new-device sign-in alert |
| Security warnings | ✅ | Alerts to every admin; account warnings to the owner |
| Email notifications | ✅ | Gmail SMTP, per-user preferences |
| Download notifications | ✅ | With a cooldown so bursts send one notice |
| Expiration reminders | ✅ | Background job reminds owners before a link expires |

Real-time delivery uses Server-Sent Events over Redis pub/sub. Verified by `test_notifications.py`.

### Module 7 – Analytics Dashboards

| Brief item | Status | Where |
|---|---|---|
| **File analytics:** storage usage, upload reports, download analytics, sharing reports | ✅ | User *File Analytics* page; admin *Reports* and *Storage analytics* |
| **Security dashboard:** login monitoring, unauthorized attempts, security event reports, audit monitoring | ✅ | Admin *Security monitoring*, *Suspicious activity*, *Audit logs* |
| **Admin dashboard:** user activity, storage utilization, security analytics, sharing reports, system monitoring | ✅ | Admin console – *User activity*, *Storage analytics*, *Reports*, *System* |

Verified by `test_analytics.py`, `test_reports_analytics.py`, `test_admin_security.py`.
Admins see file IDs, types and sizes only – never file names or contents.

---

## 3. Architecture components (brief diagram)

| Brief component | Status | TrustShare |
|---|---|---|
| Web app (React / Next.js) | ✅ | React 19 + Vite (the brief allows React.js or Next.js) |
| Admin dashboard | ✅ | Separate admin console |
| Mobile app, desktop client | ⛔ | Responsive web app instead; native apps are future work |
| Secure API gateway: SSL termination, routing | ✅ | Caddy reverse proxy |
| Gateway: authentication, validation, rate limiting, audit logging | ✅ | FastAPI dependencies and middleware |
| Auth, file, encryption, sharing, notification, analytics services | ✅ | Backend modules (one FastAPI app, layered routes → services → repositories) |
| Message queue / event bus (RabbitMQ / Kafka) | ➖ | Redis pub/sub for real-time events, in-process background scheduler; a broker is unnecessary at this scale |
| PostgreSQL, MongoDB, Redis | ✅ | All three, each for what it does best ([database.md](database.md)) |
| Encrypted file storage (S3 / Azure Blob) | ✅ | Azure Blob Storage in use; S3 API supported |
| Email service (SendGrid) | ➖ | Gmail SMTP with an app password |
| Push notifications (FCM) | ➖ | Server-Sent Events + browser desktop notifications |
| Captcha / anti-bot | ➖ | Rate limiting, account lockout and brute-force detection instead |
| Docker | ✅ | Docker Compose, 7 services |
| CI/CD pipeline (GitHub Actions) | ✅ | Lint, migrations, tests, frontend build on every push |
| NGINX web server | ➖ | Caddy (automatic TLS) |
| AWS / Azure cloud | ✅ storage · 🔄 hosting | Milestone 4 |
| Kubernetes, Prometheus + Grafana | ⛔ | Future work |
| SIEM, IDS/IPS, ML anomaly detection | ⛔ | Future work; rule-based detection is used |

---

## 4. Milestones

| Milestone | Brief tasks | Status |
|---|---|---|
| **1** – Initialization, design, core setup | Objectives, architecture, database schema, wireframes, frontend + backend setup, PostgreSQL / MongoDB / Redis, authentication + RBAC, secure upload, file dashboard | ✅ (tag `v0.1-milestone1`) |
| **2** – Encryption & secure sharing | AES-256 encryption, cloud storage, encrypted retrieval, sharing, access control, link expiration, key management, secure decryption | ✅ (tag `v0.2-milestone2`) |
| **3** – Monitoring, notifications & analytics | Activity monitoring, audit logging, notifications and alerts, reports, storage analytics, suspicious-activity detection | ✅ |
| **4** – Testing, deployment & documentation | Security testing, UI responsiveness, Docker + cloud deployment, production infrastructure, final documentation, final demo | 🔄 documentation in progress |

## 5. Tools & tech stack

| Brief | Used |
|---|---|
| Python, FastAPI, SQLAlchemy, Pydantic, Alembic, Uvicorn, Cryptography, Redis | ✅ all |
| React.js / Next.js, Tailwind CSS, Axios, JWT | ✅ React (Vite), Tailwind CSS, Axios, JWT |
| PostgreSQL, MongoDB, Redis | ✅ |
| JWT, OAuth2, AES-256, bcrypt, HTTPS/TLS, secure token generation | ✅ |
| AWS S3 / Azure Blob Storage, Docker, AWS / Azure | ✅ Azure Blob + S3 API, Docker · 🔄 cloud hosting |
| VS Code, Git + GitHub, Docker Compose, Postman, monitoring & logging | ✅ (structured request logs, health checks, admin system page) |

## 6. Performance metrics

The brief's performance metrics (encryption speed, upload / download time, API response time,
concurrent users, detection accuracy) will be measured and reported in Milestone 4.

## 7. Testing summary

- **318 backend tests** (pytest). 315 run everywhere; 3 Azure Blob tests run in CI against
  Microsoft's Azurite emulator and are skipped on machines without it.
- **Postman collections:** Milestone 2 (30 requests, 49 checks) and Milestone 3 (47 requests,
  77 checks).
- **GitHub Actions CI** on every push: ruff, migrations, tests, ESLint, Prettier, production build.
