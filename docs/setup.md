# TrustShare – Setup and Configuration

How to run TrustShare locally, configure storage and email, create accounts, and run the tests.

## Prerequisites

- Docker and Docker Compose
- For running outside Docker: Python 3.12+ and Node.js 20+

## Run with Docker

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

## HTTPS (local)

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

## Using real AWS S3 instead of RustFS

The code speaks the plain S3 API, so switching is configuration only:

1. AWS console → **S3** → create a bucket (e.g. in `ap-south-1`), keep **Block all public access**
   on, default encryption SSE-S3 on (an extra layer – the objects are already AES-256-GCM encrypted).
2. **IAM** → create a user for the app (no console access) with the least-privilege policy in
   [aws-iam-policy.json](aws-iam-policy.json) (replace `YOUR-BUCKET-NAME`), then create an
   access key for it.
3. In `.env`: `S3_ENDPOINT_URL=` (empty), `S3_REGION=ap-south-1`, `S3_BUCKET=<bucket>`,
   `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` = the new key → `docker compose up -d --force-recreate backend`.
4. Copy the existing encrypted objects across (no decryption needed – file keys stay valid):
   `docker compose exec backend python -m app.scripts.copy_objects --from-endpoint http://rustfs:9000`

Switching back = restore the RustFS values in `.env` and recreate the backend.

## Using Azure Blob Storage

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

## Create an admin and demo data

```bash
# First Admin (the password is asked for interactively)
docker compose exec backend python -m app.scripts.create_admin --email you@example.com --name "Admin"

# Optional demo data: a User and a Guest account, sample folders and files
docker compose exec backend python -m app.scripts.seed_demo
```

The seed script asks for one password used by both demo accounts (`user@example.com`, `guest@example.com`) and is safe to run more than once.

## Run tests and linters

```bash
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec frontend npm run lint
```

## Postman collection

`postman/TrustShare_M2.postman_collection.json` checks encrypted upload and download, access control,
share links (view vs download, limit, revoke, expiry), direct sharing, admin RBAC and analytics – 30
requests, run in order. Import it with `postman/TrustShare_local.postman_environment.json` into
Postman (Collection Runner), or run it with Newman in Docker:

```bash
docker run --rm --network trustshare_default -v "$PWD/postman:/etc/newman" postman/newman:6-alpine run TrustShare_M2.postman_collection.json -e TrustShare_local.postman_environment.json --env-var baseUrl=http://backend:8000/api
```

It creates two throwaway accounts (`@postman.example.com`); remove them afterwards with
`docker compose exec backend python -m app.scripts.remove_test_accounts postman.example.com`.

`postman/TrustShare_M3.postman_collection.json` checks Milestone 3 – activity monitoring, audit logs (incl. the hash-chain verification), notifications, the brute-force alert and its workflow, reports and storage analytics – 47 requests, 77 checks. Admin endpoints need an admin, which can't be created through the API: fill `adminEmail` / `adminPassword` in the environment, or pass them to Newman with `--env-var adminEmail=… --env-var adminPassword=…`. Run it from the repository root (the upload step reads `postman/sample-report.pdf`):

```bash
docker run --rm --network trustshare_default -v "$PWD/postman:/etc/newman" postman/newman:6-alpine run TrustShare_M3.postman_collection.json -e TrustShare_local.postman_environment.json --env-var baseUrl=http://backend:8000/api --env-var adminEmail=… --env-var adminPassword=…
```

Run one collection at a time, at least a minute apart: sign-ins are rate-limited to 10 per minute per IP address, and the M3 collection's brute-force test needs its six wrong passwords to reach the server (straight after another run, the limiter answers `429` first and no alert is raised – the protection working, not a failure). Remove the test accounts afterwards with `docker compose exec backend python -m app.scripts.remove_test_accounts postman.example.com`.

## Environment variables

See [.env.example](../.env.example).

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
| `MASTER_KEYS` / `ACTIVE_MASTER_KEY_VERSION` | Versioned 256-bit master keys (`1:<base64>,2:<base64>`) that wrap every file key, and the one used for new files – back them up separately; see [key-management.md](key-management.md) |
| `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_REGION` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Object storage for the encrypted files (empty endpoint = real AWS S3) |
| `RUSTFS_ACCESS_KEY` / `RUSTFS_SECRET_KEY` | Credentials of the local RustFS container |
| `STORAGE_PROVIDER` / `AZURE_STORAGE_CONNECTION_STRING` / `AZURE_CONTAINER` | `s3` (default) or `azure`; the Azure storage account's connection string and private container |

Milestone 3 settings (optional): detection thresholds `DETECT_FAILED_LOGINS_LIMIT`/`_MINUTES` (5 / 10), `DETECT_UNAUTHORIZED_*` (4 / 10), `DETECT_DOWNLOADS_*` (20 / 5), `DETECT_EXPIRED_LINK_*` and `DETECT_REVOKED_LINK_*` (2 / 10) – an alert fires when the count goes above the limit; `SCHEDULER_ENABLED` (true), `SCHEDULER_INTERVAL_SECONDS` (300), `LINK_REMINDER_HOURS` (24), `DOWNLOAD_NOTICE_COOLDOWN_MINUTES` (10), `ADMIN_ALERT_EMAIL_COOLDOWN_MINUTES` (15), `SSE_HEARTBEAT_SECONDS` (25), `SSE_MAX_SECONDS` (3600).

Optional settings with defaults include `MAX_UPLOAD_MB` (25), `DEFAULT_QUOTA_MB` (1024), `ZIP_MAX_FILES` (100), `ZIP_MAX_MB` (250), `ACCESS_TOKEN_TTL_MINUTES` (15), `REFRESH_TOKEN_TTL_DAYS` (7), `MAX_FAILED_LOGINS` (5), `LOCKOUT_MINUTES` (15), `SHARE_LINK_MAX_DAYS` (30), `SHARE_LINK_RATE_LIMIT_PER_MINUTE` (60) and `INACTIVE_ACCOUNT_DAYS` (30).

> **Never commit `.env` files or secrets.**


## Troubleshooting

| Problem | Fix |
|---|---|
| `failed to connect to the docker API` | Docker Desktop isn't running – start it and wait until it says *Engine running* |
| Port 5432 already in use | Another PostgreSQL runs on the machine; the compose file maps the container to host port **5433** |
| Browser warns about the certificate on https://localhost:8443 | Trust Caddy's local root certificate (see *HTTPS (local)* above) |
| `429 Too Many Requests` on sign-in | Sign-ins are limited to 10 per minute per IP address – wait a minute |
| Account locked after wrong passwords | Wait 15 minutes, or an admin unlocks it under *User management* |
| Emails don't arrive | Without `SMTP_USER` / `SMTP_PASSWORD` emails are written to the backend log: `docker compose logs backend` |
| Frontend changes don't show after editing `package.json` | `docker compose up -d --build --renew-anon-volumes frontend` |
| Backend won't start after pulling changes | `docker compose logs backend` – migrations run on start; check `.env` has every variable from `.env.example` |
