# TrustShare – Requirements (Milestone 1)

> Scope: Milestone 1 (Weeks 1–2). Items marked **(M2)**, **(M3)**, **(M4)** are designed for now but built later.

## 1. Problem & objective

Organisations exchange sensitive documents through email attachments and public cloud links that have no expiry, no access control and no audit trail. **TrustShare** is a private, secure file-sharing platform where users upload, organise and (from M2) share files through encrypted, permission-controlled, time-limited links, with every action logged.

**Milestone 1 objective:** a working foundation – secure authentication with roles, a validated file-upload pipeline with metadata indexing, and a Drive-like dashboard – running locally in Docker.

## 2. Actors & roles

| Role | Who | Summary |
|---|---|---|
| **Admin** | Platform operator | Manages users and roles, can view every user's files and the activity log. |
| **User** | Standard registered member (default on sign-up) | Uploads and manages **own** files and folders. |
| **Guest** | Known external person with an account (role assigned by an Admin) | Logs in, read-only: can view/download files available to them, cannot upload, create folders or modify anything. Every action is traceable to their account. |
| **Link visitor** **(M2)** | Anyone holding a public share link – no account, not logged in | Can open only that one file, within the link's limits (expiry, download count, optional password). Not a role; identified only by IP in the logs. |

Every request is authorised by **permission**, not by role name. Roles are bundles of permissions, so adding a role later (e.g. "Auditor") needs no code change.

**Guest vs Link visitor:** a Guest is a logged-in role used for "Restricted" sharing (specific known people, fully traceable). A Link visitor uses "Anyone with the link" sharing (convenient, no account). In M2 the file owner chooses the access mode for each share link.

## 3. Permission matrix

| Permission | Meaning | Admin | User | Guest |
|---|---|:-:|:-:|:-:|
| `file:read` | List, preview, download own (and later shared) files | ✅ | ✅ | ✅ |
| `file:upload` | Upload new files | ✅ | ✅ | ❌ |
| `file:update` | Rename, move, trash/restore own files | ✅ | ✅ | ❌ |
| `file:delete` | Permanently delete own files | ✅ | ✅ | ❌ |
| `folder:manage` | Create, rename, move, delete folders | ✅ | ✅ | ❌ |
| `file:read_all` | See any user's files | ✅ | ❌ | ❌ |
| `user:read` | List users | ✅ | ❌ | ❌ |
| `user:manage` | Change role, activate/deactivate, unlock users | ✅ | ❌ | ❌ |
| `audit:read` | View activity logs of all users | ✅ | ❌ | ❌ |
| `share:create` **(M2)** | Create secure share links | ✅ | ✅ | ❌ |

Ownership rule: even with `file:update`, a user can only act on files where `owner_id == current_user.id`, unless they hold `file:read_all` (read) – admins do not silently modify other people's files.

## 4. Functional requirements

### 4.1 Authentication & account (FR-A)
| ID | Requirement | Priority |
|---|---|---|
| FR-A1 | Register with full name, email, password. Email unique (case-insensitive). | Graded |
| FR-A2 | Password policy: ≥ 10 chars, upper + lower + digit + symbol, not equal to email. Stored as **bcrypt** hash (cost 12). | Graded |
| FR-A3 | Email verification link (24 h, single use) sent on sign-up; unverified users cannot log in. | Extra |
| FR-A4 | Login returns a **JWT access token (15 min)** + a **rotating refresh token (7 days)** in an HttpOnly cookie. | Graded |
| FR-A5 | Refresh endpoint rotates the refresh token; reuse of an old refresh token revokes all sessions of that user (theft detection). | Extra |
| FR-A6 | Logout (current device) and Logout-all (every device). | Extra |
| FR-A7 | Account lockout for 15 min after 5 consecutive failed logins; rate limiting on auth endpoints. | Extra |
| FR-A8 | Forgot password → emailed single-use reset link valid 15 min; reset revokes all sessions. | Graded (UI) |
| FR-A9 | **TOTP MFA**: enable via QR code (Google Authenticator), confirm with a code, receive 10 one-time backup codes; login asks for a code when MFA is on; disable requires password + code. | Graded ("MFA foundations") |
| FR-A10 | **Google login (OAuth2 / OpenID Connect)**; links to an existing account with the same verified email, otherwise creates a User. | Graded ("OAuth foundations") |
| FR-A11 | `GET /me` returns profile, role and permissions; frontend shows/hides features accordingly. | Graded |

### 4.2 RBAC & administration (FR-R)
| ID | Requirement |
|---|---|
| FR-R1 | Every protected API route declares the permission it needs; missing token → **401**, insufficient permission → **403**. |
| FR-R2 | Admin users page: list/search users, change role, activate/deactivate, unlock. |
| FR-R3 | An admin cannot demote or deactivate themselves (prevents lock-out of the last admin). |

### 4.3 File upload & storage (FR-U)
| ID | Requirement |
|---|---|
| FR-U1 | Allowed types: PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG/JPEG. |
| FR-U2 | Max size **25 MB** per file (configurable via env). Checked while streaming, not after. |
| FR-U3 | Type checked by **file content (magic bytes)** and extension together – a renamed `.exe` is rejected. |
| FR-U4 | Original filename sanitised for display; file saved on disk under a random server-generated name (no path traversal). |
| FR-U5 | SHA-256 hash computed on upload; duplicate upload of identical content in the same folder is flagged. |
| FR-U6 | Per-user storage quota (default 1 GB, configurable). Upload rejected when exceeded. |
| FR-U7 | Metadata (original name, size, MIME type, owner, folder, hash, timestamps) saved in **MongoDB**. |
| FR-U8 | Storage goes through a `StorageBackend` interface (`save / open / delete`). M1 = local disk; **(M2)** = AES-256-GCM encryption + AWS S3, with no changes to callers. |

### 4.4 File & folder management (FR-F)
| ID | Requirement |
|---|---|
| FR-F1 | Nested folders: create, rename, move, delete (to trash); breadcrumb navigation. |
| FR-F2 | File list with name, type, size, upload date, actions; list and grid views; sort by name/size/date. |
| FR-F3 | Search by name; filter by category (Documents, Spreadsheets, Presentations, Images, Text) and date. |
| FR-F4 | Rename, move, download, preview (images & PDF in browser). |
| FR-F5 | Trash: soft delete, restore, permanent delete, "empty trash". Trashed files still count toward quota until permanently deleted. |
| FR-F6 | Storage meter: used / quota. |

### 4.5 Activity logging (FR-L)
| ID | Requirement |
|---|---|
| FR-L1 | Log to MongoDB: register, login success/failure, logout, MFA changes, password reset, upload, download, rename, move, trash, restore, delete, role changes. |
| FR-L2 | Each entry: user, action, resource, IP address, user agent, result, timestamp. Append-only (no update/delete API). |
| FR-L3 | User sees own recent activity; Admin sees all. **(M3)** adds alerts, reports and suspicious-activity rules on top of this data. |

### 4.6 Frontend (FR-UI)
Auth screens (login, sign-up, verify email, forgot/reset password, MFA step, Google button); dashboard with sidebar, top search, storage meter, user menu; upload modal with drag-and-drop, multiple files, per-file progress and error messages; folder navigation with breadcrumbs; trash; preview; settings (profile, password, MFA); admin users page. Every view has loading, empty and error states, and works on mobile width.

## 5. Non-functional requirements

| Area | Requirement |
|---|---|
| Security | OWASP basics: hashed passwords, signed short-lived tokens, HttpOnly + SameSite refresh cookie, CORS restricted to the frontend origin, input validation with Pydantic, no secrets in git, generic auth error messages (no user enumeration). |
| Performance | Typical API response < 200 ms locally; uploads streamed to disk in chunks (memory use does not grow with file size). |
| Reliability | `/health` reports status of PostgreSQL, MongoDB and Redis; services restart automatically in Docker. |
| Maintainability | Layered backend (routers → services → repositories), typed Python, ruff, ESLint/Prettier, pre-commit, CI on every push, Alembic migrations. |
| Testability | pytest suite for auth, RBAC and upload validation; seed script creating Admin/User/Guest accounts and sample files. |
| Usability | Clean light Drive-like UI, responsive, accessible labels, toast feedback for every action. |
| Portability | One command (`docker compose up`) starts the full stack. |

## 6. User stories (M1)

1. *As a visitor*, I can create an account and verify my email, so that only real addresses get access.
2. *As a user*, I can log in with email + password (and an authenticator code if I enabled MFA), so that my files are protected even if my password leaks.
3. *As a user*, I can sign in with Google, so that I don't need another password.
4. *As a user*, I can reset a forgotten password through my email.
5. *As a user*, I can upload PDFs, Office documents and images up to 25 MB and see progress, so I know when the upload has finished.
6. *As a user*, I am told clearly when a file is rejected (wrong type, too large, quota full).
7. *As a user*, I can organise files into folders, search, filter, rename, move, preview and download them.
8. *As a user*, I can move files to trash and restore them if I made a mistake.
9. *As a user*, I can log out of every device if I think my account is compromised.
10. *As a guest*, I can browse and download files available to me but cannot upload or change anything.
11. *As an admin*, I can see all users, change their roles, deactivate or unlock them.
12. *As an admin*, I can see the activity log to investigate what happened.
13. *As a link visitor* **(M2)**, I can open a file someone shared with me through a secure link without creating an account, until the link expires or reaches its download limit.

## 7. Acceptance criteria – Milestone 1 demo checklist

| # | Graded item | How we prove it |
|---|---|---|
| 1 | DB services in Docker, connected to FastAPI | `docker compose ps` shows all services healthy; `GET /health` returns `ok` for postgres, mongo, redis. |
| 2 | Register → login → JWT → role-restricted routes | Register in UI → login (with MFA) → show access token in DevTools → `GET /api/admin/users` as User returns **403**, as Admin returns **200**. |
| 3 | Upload via UI passes size/type checks, saved, metadata in MongoDB | Upload a PDF → appears in list → file on disk under `storage/` → document visible in MongoDB Compass (`files` collection). Upload a renamed `.exe` and a 30 MB file → both rejected. |
| 4 | Dashboard with file management + folders | Create folder → navigate via breadcrumbs → search/filter → rename/move/trash/restore. |

## 8. Out of scope (future work)

From the reference architecture diagram, deliberately **not** built in this internship: mobile app, desktop sync client, message queue (RabbitMQ/Kafka), Kubernetes, SIEM / IDS, ML anomaly detection (M3 uses rule-based detection instead), push notifications (FCM), captcha. These are listed in the final report as future scope.
