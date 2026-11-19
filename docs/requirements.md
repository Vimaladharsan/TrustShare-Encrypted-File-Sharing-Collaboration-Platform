# TrustShare – Requirements

> Final requirements for Milestones 1–3, with the status of each item. The **Built in** column shows
> the milestone that delivered it. Milestone 4 (testing, deployment, documentation) is tracked in the
> [brief coverage](brief-coverage.md).

## 1. Problem and objective

Organisations exchange sensitive documents through email attachments and public cloud links that
have no expiry, no access control and no audit trail. **TrustShare** is a private, secure
file-sharing platform where users upload, organise and share files through encrypted,
permission-controlled, time-limited links – with every action logged, suspicious behaviour detected
and administrators given a complete monitoring console without access to anyone's files.

| Milestone | Objective |
|---|---|
| 1 | A working foundation: authentication with roles and MFA, a validated upload pipeline, a Drive-like dashboard – in Docker |
| 2 | Server-side AES-256 encryption with key management, cloud storage, secure sharing with expiry and permissions, dashboards, HTTPS |
| 3 | Activity monitoring, tamper-evident audit logs, notifications and alerts, reports, storage analytics, suspicious-activity detection |
| 4 | Security testing, cloud deployment, final documentation and demonstration |

## 2. Actors and roles

| Role | Who | Summary |
|---|---|---|
| **Admin** | Platform operator | Manages accounts (roles, disable, unlock), monitors activity, audit logs, alerts, reports and analytics. **Cannot open other users' files or see their names.** May delete accounts inactive for 30+ days, with their files. Manages only their own files like a User. |
| **User** | Registered member (default on sign-up) | Uploads, organises and shares **own** files; receives shares from others. |
| **Guest** | Known external person with an account (role set by an Admin) | Read-only: views and downloads files shared with them; cannot upload, create folders or share. Every action is traceable to the account. |
| **Link visitor** | Anyone holding a share link – no account | Opens only that one file, within the link's limits (permission, expiry, download limit, optional password, revocation). Not a role; identified by IP address in the logs. |

Every request is authorised by **permission**, not by role name. Roles are bundles of permissions,
so a new role (e.g. "Auditor") needs no code change.

## 3. Permission matrix

| Permission | Meaning | Admin | User | Guest |
|---|---|:-:|:-:|:-:|
| `file:read` | List, preview, download own files and files shared with you | ✅ | ✅ | ✅ |
| `file:upload` | Upload new files | ✅ | ✅ | ❌ |
| `file:update` | Rename, move, trash / restore own files | ✅ | ✅ | ❌ |
| `file:delete` | Permanently delete own files | ✅ | ✅ | ❌ |
| `folder:manage` | Create, rename, move, delete folders | ✅ | ✅ | ❌ |
| `share:create` | Create, edit and revoke shares | ✅ | ✅ | ❌ |
| `user:read` | List accounts, admin overview | ✅ | ❌ | ❌ |
| `user:manage` | Change role, disable / enable, unlock accounts | ✅ | ❌ | ❌ |
| `user:delete_inactive` | Delete an account inactive for 30+ days, with all its files | ✅ | ❌ | ❌ |
| `audit:read` | Activity monitoring, audit logs, security events, alerts, reports, analytics | ✅ | ❌ | ❌ |

**Ownership rule:** every file action requires that the file belongs to the current user, or a
valid share. There is **no admin bypass** – the Milestone 1 permission `file:read_all` was removed
in Milestone 2 (migration `c4d8e2a6b9f0`). Other users' files answer `404`, so their existence is
not revealed.

## 4. Functional requirements

All items below are implemented (✅). Where they are tested: [brief-coverage.md](brief-coverage.md).

### 4.1 Authentication and account (FR-A)

| ID | Requirement | Built in |
|---|---|---|
| FR-A1 | Register with full name, email and password; email unique (case-insensitive); the same answer for new and existing emails, so sign-up can't reveal who has an account | M1 |
| FR-A2 | Password policy: at least 10 characters with upper case, lower case, digit and symbol, not equal to the email; stored as a **bcrypt** hash (cost 12) | M1 |
| FR-A3 | Email verification link (24 h, single use) on sign-up; unverified users see a reminder (or are blocked with `REQUIRE_EMAIL_VERIFICATION=true`) | M1 |
| FR-A4 | Login returns a **JWT access token (15 min)** and a **rotating refresh token (7 days)** in an HttpOnly cookie | M1 |
| FR-A5 | Reusing an old refresh token ends every session of the account (theft detection) | M1 |
| FR-A6 | Log out of this device, of one chosen device, or of every device | M1, M2 |
| FR-A7 | Account lockout for 15 min after 5 failed logins; per-IP rate limits on sign-in and registration | M1 |
| FR-A8 | Forgot password: emailed single-use reset link valid 15 min; resetting ends every session | M1 |
| FR-A9 | **TOTP two-step verification:** QR-code setup, confirm with a code, 10 one-time backup codes; login asks for a code; turning it off needs password + code; backup codes can be replaced | M1, M2 |
| FR-A10 | **Google sign-in** (OAuth 2.0 / OpenID Connect with PKCE); links to an existing account with the same verified email, otherwise creates a User | M1 |
| FR-A11 | `GET /api/users/me` returns profile, role and permissions; the UI shows or hides features accordingly (the backend enforces them regardless) | M1 |
| FR-A12 | My account: edit name, change password, signed-in devices, delete my account (erases files, keys, shares and sessions; keeps the audit trail) | M2 |
| FR-A13 | Sign-in from a new device or IP address notifies the owner, with a *Was this you?* check | After M3 |
| FR-A14 | Account security score (0–100) from seven checks, each with a *Fix now* action | After M3 |

### 4.2 Roles and administration (FR-R)

| ID | Requirement | Built in |
|---|---|---|
| FR-R1 | Every protected route declares the permission it needs; no token → `401`, missing permission → `403` | M1 |
| FR-R2 | Admin user management: list and search accounts, change role, disable / enable, unlock | M1 |
| FR-R3 | An admin can't demote, disable or delete themselves, or the last admin | M1 |
| FR-R4 | Admins can't open users' files; they may delete accounts inactive for 30+ days, with their files | M2 |

### 4.3 File upload and storage (FR-U)

| ID | Requirement | Built in |
|---|---|---|
| FR-U1 | Allowed types: PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG / JPEG | M1 |
| FR-U2 | Max **25 MB** per file (configurable), checked while streaming | M1 |
| FR-U3 | Type checked by **content** (magic bytes and Office file structure) and extension together – a renamed `.exe` is rejected | M1 |
| FR-U4 | Original name sanitised for display; stored under a random server-generated name | M1 |
| FR-U5 | SHA-256 fingerprint; an identical upload in the same folder is flagged and the user may *Keep both* | M1 |
| FR-U6 | Per-user storage quota (default 1 GB, configurable) | M1 |
| FR-U7 | Metadata (name, size, type, category, owner, folder, hash, dates) stored in **MongoDB** | M1 |
| FR-U8 | Storage behind an interface, so encryption and cloud storage were added without changing callers | M1, M2 |

### 4.4 File and folder management (FR-F)

| ID | Requirement | Built in |
|---|---|---|
| FR-F1 | Nested folders: create, rename, move, trash, delete; breadcrumb navigation | M1 |
| FR-F2 | File table with name, type, size and date, sortable; folders as cards | M1 |
| FR-F3 | Search by name across all folders; filter by category (documents, spreadsheets, presentations, images, text) | M1 |
| FR-F4 | Rename, move (menu or drag and drop), download, in-app preview of PDF, images and text | M1, after M3 |
| FR-F5 | Trash: restore, permanent delete, bulk actions, empty trash; trashed files count toward the quota | M1 |
| FR-F6 | Storage meter and storage page (by type, largest files) | M1, M2 |
| FR-F7 | Multi-select: move, trash or download several files as one ZIP (decrypted on the fly) | After M3 |
| FR-F8 | Favorites and Recent files | M2 |

### 4.5 Encryption and key management (FR-E)

| ID | Requirement | Built in |
|---|---|---|
| FR-E1 | Every file encrypted on the server with **AES-256-GCM** using its own random 256-bit key, in authenticated 1 MiB chunks | M2 |
| FR-E2 | File keys stored only **wrapped** by a versioned master key (envelope encryption); keys never appear in responses, logs or the browser | M2 |
| FR-E3 | Encrypted bytes in private cloud storage (Azure Blob Storage or S3); metadata in MongoDB; wrapped keys in PostgreSQL | M2 |
| FR-E4 | Decryption only in memory after authorization; integrity verified; tampering returns a safe error | M2 |
| FR-E5 | Key rotation re-wraps file keys without re-encrypting files; permanent delete destroys the key | M2 |

Details: [key-management.md](key-management.md).

### 4.6 Secure sharing (FR-S)

| ID | Requirement | Built in |
|---|---|---|
| FR-S1 | Share links for anyone: view-only or view & download, expiry (max 30 days), optional download limit, instant revoke | M2 |
| FR-S2 | Link tokens are 256-bit random values stored only as SHA-256 hashes and hidden in logs | M2 |
| FR-S3 | Direct sharing with registered users ("Shared with me" / "Shared by me") | M2 |
| FR-S4 | Every access re-checks revocation, expiry, limit, file status and the owner's account and permissions | M2 |
| FR-S5 | Edit a share (permission, expiry, limit) without changing the link | After M3 |
| FR-S6 | Optional link password (bcrypt hash; 5 wrong tries lock that visitor out for 15 min) | After M3 |
| FR-S7 | Share several files or a whole folder at once; QR code for links | After M3 |
| FR-S8 | Access history per share: opens, views, downloads and refused attempts with the reason | After M3 |

### 4.7 Secure vault (FR-V)

| ID | Requirement | Built in |
|---|---|---|
| FR-V1 | A per-user vault with its own password; each file key additionally sealed with a key derived from that password (scrypt); file names encrypted | M2 |
| FR-V2 | The vault password is required for every action and never stored; 5 wrong tries lock the vault for 15 min | M2 |
| FR-V3 | Vault files are private only: never shared, searched or listed in Recent | M2 |

### 4.8 Activity monitoring and audit (FR-L)

| ID | Requirement | Built in |
|---|---|---|
| FR-L1 | Every important action recorded automatically: logins (success / failure), logouts, uploads, downloads, previews, sharing, link creation / expiry / revocation, unauthorized attempts, admin actions | M1, M3 |
| FR-L2 | Each entry: user, activity type, file ID, status, IP address, device, time; append-only | M1, M3 |
| FR-L3 | Separate **audit log**, each entry SHA-256 **hash-chained** to the previous one; a verify check detects any change or deletion | M3 |
| FR-L4 | Admin activity monitoring with filters and a live feed; audit log filters (user, type, file, status, dates, exact time window) and CSV export | M3 |
| FR-L5 | Users see their own activity log | M2 |

### 4.9 Notifications (FR-N)

| ID | Requirement | Built in |
|---|---|---|
| FR-N1 | In-app notifications delivered in real time (Server-Sent Events) | M3 |
| FR-N2 | Email notifications according to each user's preferences | M3 |
| FR-N3 | Events: file or folder shared with you, your shared file downloaded, link expiring soon / expired, account security warnings | M3 |
| FR-N4 | Security alerts to every admin for detected threats and high-severity events | M3 |
| FR-N5 | Optional desktop pop-ups while TrustShare is in a background tab | After M3 |

### 4.10 Suspicious-activity detection (FR-D)

| ID | Requirement | Built in |
|---|---|---|
| FR-D1 | Rules with sliding windows (thresholds configurable): more than 5 failed sign-ins in 10 min, repeated unauthorized access, more than 20 downloads in 5 min, repeated use of expired or revoked links | M3 |
| FR-D2 | One alert per rule and subject per window (no alert floods) | M3 |
| FR-D3 | Alert workflow: open → acknowledged → resolved, with notes; every change audited | M3 |
| FR-D4 | From an alert, open everything that user (or IP) did 30 minutes before and after | After M3 |

### 4.11 Analytics and reports (FR-AN)

| ID | Requirement | Built in |
|---|---|---|
| FR-AN1 | User File Analytics: storage by type, uploads, downloads (incl. unique users), sharing trends, date range | M2 |
| FR-AN2 | Admin security dashboard: logins, failed and unauthorized attempts, blocked requests, security events by severity | M2 |
| FR-AN3 | Admin reports: uploads, downloads, sharing, per-user activity, security – with filters and CSV export | M3 |
| FR-AN4 | Admin storage analytics: total and per-user storage, file, download and sharing statistics | M3 |
| FR-AN5 | All admin views show file IDs, types and sizes only – never file names | M3 |

### 4.12 User interface (FR-UI)

Auth screens (sign-in, sign-up, verify email, forgot / reset password, two-step step, Google
button); a workspace with sidebar, search, storage meter, notifications and account menu; upload
dialog with drag and drop and per-file progress; folders with breadcrumbs; preview; sharing
dialogs; vault; analytics; settings; a separate admin console. Every view has loading, empty and
error states, works at phone width, and supports light and dark mode.

## 5. Non-functional requirements

| Area | Requirement |
|---|---|
| Security | Encryption at rest (AES-256-GCM) and in transit (TLS 1.3); hashed passwords; short-lived signed tokens; HttpOnly SameSite refresh cookie; CORS limited to the frontend; input validation (Pydantic); security headers and `Cache-Control: no-store`; no secrets in git; generic sign-in errors (no account enumeration) |
| Privacy | Admins never see file names or contents; link tokens and IP addresses masked where shown |
| Integrity | Authenticated encryption detects tampered files; hash-chained audit log detects edited or deleted entries |
| Performance | Uploads and downloads streamed in chunks (memory does not grow with file size); typical API response well under 200 ms locally. Measured in Milestone 4 |
| Reliability | Health check for PostgreSQL, MongoDB, Redis and storage; containers restart automatically; recording a log or notification never breaks the user's request |
| Maintainability | Layered backend (routes → services → repositories), typed Python, ruff, ESLint, Prettier, pre-commit, Alembic migrations, CI on every push |
| Testability | 318 automated backend tests, Postman collections, demo-data script |
| Usability | Clean, responsive UI with feedback for every action; light and dark mode |
| Portability | One command (`docker compose up`) starts all 7 services |

## 6. User stories

1. *As a visitor*, I can create an account and verify my email, so that only real addresses get access.
2. *As a user*, I can sign in with my password and an authenticator code, so my files stay safe even if my password leaks.
3. *As a user*, I can sign in with Google, so I don't need another password.
4. *As a user*, I can reset a forgotten password through my email.
5. *As a user*, I can upload documents and images and see progress, and I'm told clearly why a file is rejected.
6. *As a user*, I can organise files into folders, search, filter, preview, rename, move and download them.
7. *As a user*, I know my files are stored encrypted, so a leak of the storage alone reveals nothing.
8. *As a user*, I can share a file through a link that expires, allows only viewing, or works a limited number of times – and revoke it at any moment.
9. *As a user*, I can see who opened or downloaded my shared file, and I'm notified when it is downloaded.
10. *As a user*, I can keep my most sensitive files in a vault that needs a second password.
11. *As a user*, I'm warned when my account signs in from a new device.
12. *As a guest*, I can view and download files shared with me but cannot upload or change anything.
13. *As a link visitor*, I can open a shared file without an account until the link expires, is revoked or reaches its limit.
14. *As an admin*, I can manage accounts – change roles, disable, unlock – without being able to read anyone's files.
15. *As an admin*, I'm alerted when someone tries to break into an account or abuses links, and I can investigate and resolve the alert.
16. *As an admin*, I can prove the audit log hasn't been tampered with, and export it.
17. *As an admin*, I can see reports and storage analytics across the platform.

## 7. Acceptance criteria (graded items)

| Milestone | Graded item | How it is shown |
|---|---|---|
| 1 | Databases in Docker, connected to FastAPI | `GET /api/health` returns `ok` for every service |
| 1 | Register → login → JWT → role-restricted routes | A User calling an admin route gets `403`; an Admin gets `200` |
| 1 | Upload passes size / type checks, metadata in MongoDB | A PDF is accepted; a renamed `.exe` and an oversized file are rejected |
| 1 | Dashboard with file and folder management | Folders, breadcrumbs, search, filter, rename, move, trash, restore |
| 2 | Encryption and secure sharing | The stored object is ciphertext; the owner downloads the original |
| 2 | Access control and permissions | View-only link can't download; others' files return `404` |
| 2 | Temporary link expiration | Expired, revoked and used-up links return `410` |
| 2 | Secure storage integration | Encrypted objects in Azure Blob Storage |
| 3 | Monitoring and notifications | Live activity feed; share and download notifications in real time and by email |
| 3 | Audit logging and activity tracking | Audit log shows *Integrity verified*; filters and CSV export |
| 3 | Analytics dashboards and reports | Reports and storage analytics with charts |
| 3 | Security monitoring workflows | Six wrong passwords raise a brute-force alert; the admin resolves it |

## 8. Out of scope (future work)

From the brief's reference architecture, deliberately not built in this internship: file version
history, mobile and desktop apps, a message broker (RabbitMQ / Kafka), Kubernetes, Prometheus /
Grafana, SIEM and IDS / IPS, ML anomaly detection (rule-based detection is used), push
notifications through FCM (browser notifications are used), captcha (rate limiting and lockout are
used).
