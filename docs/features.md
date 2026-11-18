# TrustShare – Features

The complete feature list, grouped by area. For a short overview see the [README](../README.md);
for where each item of the project brief is implemented and tested see
[brief-coverage.md](brief-coverage.md).

| Area | Built in |
|---|---|
| Authentication, roles, secure upload, file dashboard | Milestone 1 (extended later) |
| Encryption, storage, sharing, vault, dashboards | Milestone 2 |
| Monitoring, audit logs, notifications, alerts, reports, analytics | Milestone 3 |
| Polish: multi-select, folder sharing, link passwords, QR codes, access history, dark mode, security score, new-device alert, drag and drop | After Milestone 3 |

## 1. Authentication and sessions
- Registration with password-strength rules (checked live in the UI and enforced on the server); passwords hashed with **bcrypt**; the same answer for new and already-registered emails (the owner gets a notice email), so sign-up can't reveal who has an account
- **JWT access tokens** (15 min, kept in memory only) and **rotating refresh tokens** (7 days, HttpOnly cookie, stored hashed in Redis) with reuse detection (a 10-second grace window lets the same browser retry a just-rotated token – two tabs or fast reloads – without being logged out)
- Logout, and **log out of all devices** from Settings
- **Change password** in Settings (confirms the current one; other devices are logged out)
- **New-device sign-in alert:** a sign-in from a browser + system the account has never used (e.g. "Chrome on Windows"), or from a new IP address, notifies the owner in the app and by email with the device and IP; the alert opens the Devices tab with a *Was this sign-in you?* check (recent devices marked **New**, sign them out, change password). A browser update is not a new device; the first sign-in of an account never alerts
- **Account security score** on My account: a 0–100 score from seven checks (two-step verification, verified email, no recent failed sign-ins, backup codes, password age, number of devices, secure vault), each with a *Fix now* button; plus an account strip with member since, files, storage, active shares and the previous sign-in
- **My account** page with Profile · Security · Devices · Account tabs: edit your display name; see every signed-in **device** (browser, OS, IP, approximate location, last active) and **sign out one device** – its access token stops working at once, not after 15 minutes; generate **new backup codes** (needs a current code, old codes stop working)
- **Delete my account**: confirmed with password (or typed email for Google-only accounts) plus a 2-step code if on; erases every file, object, wrapped key, share link, folder and session, keeps the audit trail, emails a confirmation; the last admin can't delete themselves
- **Google login** (OAuth 2.0 Authorization Code flow with PKCE): ID token verified against Google's keys; links to an existing account with the same verified email, otherwise creates a User; MFA still required if enabled
- **Email verification**: a single-use link (24 h) is emailed on sign-up; unverified users see a reminder with a Resend button (or are blocked from logging in with `REQUIRE_EMAIL_VERIFICATION=true`)
- **Forgot password**: emailed single-use reset link (15 min, stored only as a hash); resetting logs out every device
- **Two-step verification (TOTP)** with QR-code setup for Google Authenticator and one-time backup codes
- Account lockout after 5 failed logins (15 min) and per-IP rate limiting on login and registration

## 2. Roles and permissions
- **Admin**, **User** and **Guest** roles built from permissions such as `file:upload` or `user:read` – routes check permissions, not role names, so new roles need no code changes
- Guests are read-only; Admins create the first Admin from the command line, then manage users in the **Users** page: change roles, disable/enable accounts (disabled users are logged out everywhere), unlock lockouts – but never their own account or the last admin. Admins **can't open other users' files**; they can delete accounts that haven't logged in for 30+ days, with all their files
- Ownership checks on every file and folder (other users' items return 404)

## 3. Secure upload
- Allow-list of types: PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG
- **Content check** – magic bytes, plus the internal structure of Office files – so a renamed `.exe` is rejected
- 25 MB limit enforced while streaming, per-user storage quota, **SHA-256** fingerprint with duplicate detection
- Files stored under random names (the user's filename never becomes a path); metadata in MongoDB
- Upload dialog with drag and drop, several files at once, per-file progress, cancel/retry and clear error messages

## 4. File dashboard
- Drive-like layout: sidebar, search across all folders, storage meter, account menu
- Nested folders with breadcrumbs; create, rename and move files and folders
- Category filters, sortable file table, download, and **in-app preview** of PDFs, images and text files (served in a sandbox)
- **Drag and drop to move:** drag a file row onto a folder card or onto a breadcrumb (e.g. *My Files*) to move it; dragging a ticked file takes all ticked files along; folders can be dragged into other folders too (a folder can't go into itself – checked by the server). Desktop browsers; on phones the ⋮ *Move to…* menu does the same
- **Multi-select** in My Files and search: tick files, then move them, trash them or **download them as one ZIP** (decrypted on the fly into the archive – never written to disk; a ZIP counts once for the excessive-downloads rule)
- Trash with restore, bulk restore/delete, empty trash and permanent delete
- Loading, empty and error states; responsive layout
- **Light and dark mode** for the workspace (sun/moon button in the top bar, or Light / Dark / System in the account menu; remembered per browser, applied before the page paints, "System" follows the operating system live). Sign-in and share-link pages stay light; the admin console is always its own dark theme
- Buttons adapt to the user's permissions (enforced by the backend regardless)

## 5. Encryption and storage
- **AES-256-GCM** with a fresh random 256-bit key per file, in 1 MiB authenticated chunks (format "TSE1"): any changed, missing, reordered or swapped chunk is detected and the download is refused
- **Envelope encryption:** each file key is stored only wrapped by a versioned **master key** (`MASTER_KEYS`); keys never appear in responses, logs or the browser (tests check this)
- Encrypted bytes in private **object storage** – RustFS locally, **Azure Blob Storage** or **AWS S3** by configuration (`STORAGE_PROVIDER`) – metadata in MongoDB, wrapped keys in PostgreSQL – no single store reveals a file
- **Key rotation** without re-encrypting files (`python -m app.scripts.rotate_keys`), crypto-shredding on permanent delete, migration of Milestone 1 plaintext files
- Decryption only in memory, after authorization; integrity failures return a safe error – details: [key-management.md](key-management.md)

## 6. Secure sharing
- **Share links** for anyone (no account): view-only or view & download, expiry as a preset (1 hour … 30 days) or an exact date and time (max 30 days), optional download limit, instant revoke; 256-bit tokens stored only as SHA-256 hashes and hidden in logs
- **Direct sharing** with registered users ("Shared with me" / "Shared by me"); the recipient gets an email notice
- **Share several files at once** from the My Files selection: one link per file (Copy all), or one person gets all of them with a single notification and email; each file is checked on its own
- **Optional password on links:** visitors must enter it before they see anything about the file; stored only as a bcrypt hash, sent in an `X-Share-Password` header, 5 wrong tries lock that visitor out of the link for 15 minutes (shown in the access history); can be added, changed or removed later
- **Share a whole folder:** every file in the folder (sub-folders included) with the same settings – one link per file, or one person gets all of them with a single notification and email (the files in the folder now; files added later are not included)
- **QR code** for every new link, generated in the browser (the link is never sent to an online QR service), downloadable as PNG
- **Access history per share:** who opened the link, viewed or downloaded the file, when and from which device, plus refused attempts with the reason (expired, revoked, limit reached, view only); registered visitors by name, link visitors as "Anonymous visitor", IP addresses shown with the last part hidden
- **Edit a share without revoking it:** change view/download, extend or shorten the expiry (people's shares can also be set to never expire) or change the download limit – the link stays the same, an expired or used-up share becomes active again, the edit is audited and the recipient of a direct share is notified
- Every access re-checks revocation, expiry, limit, file status and the owner's account and permissions – trashing a file or disabling its owner stops all links at once

## 7. Secure vault
- A private, password-protected place per user for the most sensitive files, with a **separate vault password** (must differ from the login password)
- **Extra encryption:** each vault file's key is sealed with a key derived from the vault password (scrypt) *inside* the normal master-key envelope, and file names are encrypted too – without the vault password nobody can open them, not even someone with the database and master keys
- The password is asked for **every** action (list, open, add, rename, delete, move) and never kept; 5 wrong passwords lock the vault for 15 minutes and raise a high-severity security event
- Private only: no sharing, not in search, Recent or the normal file list; "Move to vault" / "Move to My Files" only re-lock the key (the encrypted file isn't touched)
- Change the vault password (every key re-locked) or, if it's forgotten, reset the vault (deletes its files – they can't be recovered by design); vault files count toward the storage quota and are erased with the account

## 8. Dashboards and analytics
- **User:** Dashboard, Recent, Favorites, Storage breakdown, **File Analytics** (storage by type, uploads, downloads incl. unique users and shared downloads, sharing trends, date range, change vs previous period), own Activity Logs, and a Security page
- **Admin panel:** **Security Dashboard** (logins, failed logins, unauthorized and blocked attempts, security events by severity, recent logins with IP and location), audit log viewer with **CSV export** (formula-injection safe, the export itself is audited), storage per account (sizes only – admins can't open users' files), sharing reports, system monitoring
- **Security events** recorded automatically: repeated failed logins, lockouts, suspicious IPs, new-IP sign-ins, token reuse, 403s and forged tokens, rate-limit blocks, disguised or tampered files, download anomalies, admin actions

## 9. Monitoring, notifications and alerts
New code lives in feature modules named like the brief: `activity_monitoring/`, `audit/`, `notifications/`, `reports/`, `analytics/`, `security_monitoring/`.
- **Activity monitoring:** one reusable `record_activity()` records every important action automatically (login/logout, failed logins, uploads, downloads, file access, sharing, link creation/expiry/revocation, unauthorized attempts) with user, activity type, file ID, status, IP and time; admins watch a **live feed** (Server-Sent Events)
- **Audit logs:** a separate, append-only `audit_logs` collection with the brief's fields; every entry is **hash-chained** to the one before (SHA-256), so any change or deletion is detected by `/api/audit-logs/verify`; filters by user, activity type, file ID, status and dates; CSV export; admins only
- **Notifications & alerts:** in-app notifications delivered **in real time** (SSE over Redis pub/sub, authenticated with the normal Authorization header) and by **email** per the user's preferences – file shared with you, your shared file was downloaded, link about to expire / expired (background job), account security events; **security alerts to every admin** for rule-based and high-severity events; optional **desktop pop-ups** (browser Notification API, switched on per device in Settings → Notifications) while TrustShare is in a background tab – clicking one opens the related page
- **Suspicious activity detection:** rule engine with sliding windows in Redis and thresholds in `.env` – more than 5 failed sign-ins in 10 min, repeated unauthorized access, more than 20 downloads in 5 min, repeated attempts on expired or revoked links; one alert per rule and subject per window; alert workflow open → acknowledged → resolved (with notes, audited); from any alert, **Activity around this time** opens the audit log filtered to that user (or IP) from 30 minutes before to 30 minutes after the alert
- **Reports:** uploads, downloads, sharing, one user's activity, security – summary, charts, tables and CSV export, with filters for date range, user, file type, activity type and file ID
- **Storage analytics:** total and per-user storage (incl. vaults and trash), file, download and sharing statistics with the brief's charts (storage-by-user pie, uploads by date, downloads, sharing)
- **Unified admin dashboard:** User activity · Audit logs · Security monitoring · Suspicious activity alerts · File activity reports · Storage analytics · Notification management · Users · System – in a separate **dark operations console** with its own violet/amber look, so admin mode is never confused with the user workspace
- **Privacy kept:** admins see file IDs, types and sizes in every report, log and alert – never file names (owners still see their own)
- **Screenshots** of every module: [`screenshots/m3/`](screenshots/m3/) (demo data, personal addresses masked)

## 10. Platform
- **HTTPS** through a Caddy reverse proxy (TLS 1.3) at https://localhost:8443; real client IPs via trusted proxy headers
- **Activity log** in MongoDB for every important action (plus the hash-chained audit log since Milestone 3), including **login history** (successful logins with method, failed logins with reason, lockouts) and rejected uploads (who, what, IP, user agent, request ID)
- Health endpoint that checks PostgreSQL, MongoDB, Redis and object storage
- Standard JSON error format with request IDs, security headers (`nosniff`, `X-Frame-Options: DENY`, referrer policy, `Cache-Control: no-store` so browsers never reuse a private or refused API answer – e.g. a revoked link's `410` – and every attempt reaches detection), structured logging
- Everything runs with Docker Compose; database migrations run automatically on start
