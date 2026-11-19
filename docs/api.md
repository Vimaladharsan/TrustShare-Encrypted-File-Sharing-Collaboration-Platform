# TrustShare – API Reference

TrustShare exposes **126 REST endpoints** under `/api`. This page is generated from the running
application, so paths and access rules match the code. Request and response schemas are in the
interactive documentation (Swagger UI) at http://localhost:8000/docs and in the OpenAPI schema at
http://localhost:8000/openapi.json.

## Contents

- [Conventions](#conventions) – authentication, permissions, errors, limits
- [Examples](#examples)
- [Health](#health)
- [Authentication](#authentication)
- [My account](#my-account)
- [Files](#files)
- [Folders](#folders)
- [Trash](#trash)
- [Secure vault](#secure-vault)
- [Sharing](#sharing)
- [Public share links](#public-share-links)
- [My analytics](#my-analytics)
- [Notifications](#notifications)
- [Admin – users](#admin--users)
- [Admin – security dashboard](#admin--security-dashboard)
- [Admin – activity monitoring](#admin--activity-monitoring)
- [Admin – audit logs](#admin--audit-logs)
- [Admin – security monitoring](#admin--security-monitoring)
- [Admin – reports](#admin--reports)
- [Admin – storage analytics](#admin--storage-analytics)

## Conventions

### Authentication

1. `POST /api/auth/login` returns a short-lived **access token** (15 minutes) and sets a **refresh
   token** cookie (7 days, HttpOnly, rotated on every use, stored only as a hash in Redis).
2. Send the access token on every request: `Authorization: Bearer <access token>`.
3. When it expires, `POST /api/auth/refresh` returns a new one. Reusing an old refresh token ends
   every session of the account (token-theft protection).
4. If two-step verification is on, login returns an MFA challenge instead; finish with
   `POST /api/auth/mfa/verify`.

### Who can call what

The **Access** column shows what an endpoint needs: *Public* (no account), *Signed in* (any
account), or a permission. Routes check permissions, never role names:

| Role | Permissions |
|---|---|
| Admin | `user:read`, `user:manage`, `user:delete_inactive`, `audit:read`, plus the file permissions below for their **own** files |
| User | `file:read`, `file:upload`, `file:update`, `file:delete`, `folder:manage`, `share:create` |
| Guest | `file:read` (read-only) |

A missing permission answers `403`. Admin permissions never include opening other users' files.

### Errors

Every error has the same shape; `request_id` matches the `X-Request-ID` response header and the
server log line.

```json
{ "error": { "code": "FILE_TOO_LARGE", "message": "File exceeds the 25 MB limit.", "request_id": "3f9c1a2b7d4e" } }
```

| Status | Meaning |
|---|---|
| `400` / `422` | Invalid input (validation details in `details`) |
| `401` | Not signed in, or the access token expired |
| `403` | Signed in but not allowed |
| `404` | Not found – also used for other users' files, so their existence isn't revealed |
| `409` | Conflict, e.g. a duplicate upload or a name already in use |
| `410` | Share link expired, revoked or used up |
| `413` / `415` | File too large / type not allowed or content doesn't match the extension |
| `429` | Rate limit reached, or account temporarily locked after repeated failed sign-ins – retry after the seconds in `Retry-After` |

### Limits and headers

- Sign-in and registration are rate-limited per IP; public links have their own per-IP limit.
- Uploads: 25 MB per file (configurable), per-user quota, allowed types PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG.
- Every response carries `X-Request-ID`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
  and `Cache-Control: no-store`.

## Examples

Sign in and list your files:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "user@example.com", "password": "<password>"}' | jq -r .access_token)

curl -s http://localhost:8000/api/files -H "Authorization: Bearer $TOKEN"
```

Upload a file into a folder (it is validated, encrypted and stored):

```bash
curl -s -X POST "http://localhost:8000/api/files?folder_id=<folder id>" \
  -H "Authorization: Bearer $TOKEN" -F "file=@report.pdf"
```

Create a share link that allows downloads, expires in 7 days and works at most 5 times:

```bash
curl -s -X POST http://localhost:8000/api/files/<file id>/shares \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"share_type": "link", "permission": "download", "expires_at": "2026-12-01T12:00:00Z", "max_downloads": 5}'
```

The response contains the link `url` – shown only once; the server keeps only a hash of its token.
A visitor opens it without an account: `GET /api/s/<token>`, then `GET /api/s/<token>/download`.

## Health

Checks that PostgreSQL, MongoDB, Redis and object storage are reachable.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/health` | Status of PostgreSQL, MongoDB, Redis and object storage | Public |

## Authentication

Registration, sign-in (password, two-step code, Google), token refresh, sign-out, password reset and email verification. The refresh token travels in an HttpOnly cookie limited to `/api/auth`.

| Method | Path | What it does | Access |
|---|---|---|---|
| `POST` | `/api/auth/forgot-password` | Email a password reset link (same answer whether or not the account exists) | Public |
| `GET` | `/api/auth/google/callback` | Google sends the user back here after signing in | Public |
| `GET` | `/api/auth/google/login` | Start Google login (redirects to Google) | Public |
| `POST` | `/api/auth/login` | Log in: returns tokens, or an MFA challenge if two-step verification is on | Public |
| `POST` | `/api/auth/logout` | Log out of this device | Public |
| `POST` | `/api/auth/logout-all` | Log out of every device | Signed in |
| `POST` | `/api/auth/mfa/verify` | Second login step: submit the 6-digit code (or a backup code) | Public |
| `GET` | `/api/auth/providers` | Which extra login methods are available (for the login page) | Public |
| `POST` | `/api/auth/refresh` | Swap the refresh-token cookie for a new access token (and a new cookie) | Public |
| `POST` | `/api/auth/register` | Create a new account (role: user) – same answer whether or not the email is taken | Public |
| `POST` | `/api/auth/reset-password` | Choose a new password using the link from the email (logs out every device) | Public |
| `POST` | `/api/auth/verify-email` | Confirm the email address with the link from the sign-up email | Public |
| `POST` | `/api/auth/verify-email/resend` | Send a new verification email to the logged-in user | Signed in |

## My account

Profile, password, two-step verification, signed-in devices and the security overview of the signed-in user.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/users/me` | The logged-in user's profile | Signed in |
| `PATCH` | `/api/users/me` | Update my profile (display name) | Signed in |
| `DELETE` | `/api/users/me` | Delete my account and all my files (password, 2-step code if on, typed confirmation) | Signed in |
| `GET` | `/api/users/me/mfa` | Is two-step verification on? | Signed in |
| `POST` | `/api/users/me/mfa/backup-codes` | Replace my backup codes (needs a current code; the old codes stop working) | Signed in |
| `POST` | `/api/users/me/mfa/disable` | Turn off two-step verification (needs password and a code) | Signed in |
| `POST` | `/api/users/me/mfa/enable` | Step 2: confirm with a code from the app; returns one-time backup codes | Signed in |
| `POST` | `/api/users/me/mfa/setup` | Step 1: get a QR code to scan with Google Authenticator | Signed in |
| `GET` | `/api/users/me/overview` | My security score (checklist with fixes) and account statistics | Signed in |
| `POST` | `/api/users/me/password` | Change my password (logs out every other device; this one gets a new session) | Signed in |
| `GET` | `/api/users/me/sessions` | My signed-in devices | Signed in |
| `DELETE` | `/api/users/me/sessions/{session_id}` | Sign one device out (its access stops immediately) | Signed in |

## Files

Upload (validated and encrypted), list, search, rename, move, download, preview, trash, favorites and bulk actions. Every file route checks ownership; another user's file answers `404`.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/files` | List my files | `file:read` |
| `POST` | `/api/files` | Upload a file (PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG; max 25 MB) | `file:upload` |
| `POST` | `/api/files/bulk/download` | Download the selected files as one ZIP | `file:read` |
| `POST` | `/api/files/bulk/move` | Move the selected files | `file:update` |
| `POST` | `/api/files/bulk/trash` | Move the selected files to trash | `file:update` |
| `GET` | `/api/files/favorites` | My starred files | `file:read` |
| `GET` | `/api/files/recent` | My files I recently uploaded, opened, downloaded, renamed or moved | `file:read` |
| `GET` | `/api/files/storage` | Storage page: used / available, by file type, trash, largest files | `file:read` |
| `GET` | `/api/files/usage` | My storage used vs quota | `file:read` |
| `GET` | `/api/files/{file_id}` | File details | `file:read` |
| `PATCH` | `/api/files/{file_id}` | Rename and/or move a file | `file:update` |
| `DELETE` | `/api/files/{file_id}` | Delete forever (cannot be undone) | `file:delete` |
| `GET` | `/api/files/{file_id}/download` | Download the file | `file:read` |
| `PUT` | `/api/files/{file_id}/favorite` | Star a file | `file:read` |
| `DELETE` | `/api/files/{file_id}/favorite` | Remove the star | `file:read` |
| `GET` | `/api/files/{file_id}/preview` | Show the file in the browser (PDF, images, TXT, CSV only) | `file:read` |
| `POST` | `/api/files/{file_id}/restore` | Restore from trash | `file:update` |
| `POST` | `/api/files/{file_id}/trash` | Move to trash | `file:update` |

## Folders

Nested folders: create, rename, move, trash, delete.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/folders` | List folders | `file:read` |
| `POST` | `/api/folders` | Create a folder | `folder:manage` |
| `GET` | `/api/folders/{folder_id}` | Folder details + breadcrumbs | `file:read` |
| `PATCH` | `/api/folders/{folder_id}` | Rename and/or move a folder | `folder:manage` |
| `DELETE` | `/api/folders/{folder_id}` | Delete a trashed folder and everything inside it forever (cannot be undone) | `file:delete` + `folder:manage` |
| `POST` | `/api/folders/{folder_id}/restore` | Restore from trash | `folder:manage` |
| `POST` | `/api/folders/{folder_id}/trash` | Move the folder and everything inside it to the trash | `folder:manage` |

## Trash

Restore or permanently delete trashed files and folders.

| Method | Path | What it does | Access |
|---|---|---|---|
| `POST` | `/api/trash/delete` | Permanently delete the selected items (cannot be undone) | `file:delete` |
| `POST` | `/api/trash/empty` | Permanently delete everything in the trash (cannot be undone) | `file:delete` |
| `POST` | `/api/trash/restore` | Restore the selected items | `file:update` |
| `POST` | `/api/trash/restore-all` | Restore everything in the trash | `file:update` |

## Secure vault

A second, password-protected area. File routes need the `X-Vault-Password` header on every request; 5 wrong passwords lock the vault for 15 minutes.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/vault` | Does my vault exist, and is it locked? | Signed in |
| `POST` | `/api/vault` | Create my vault with a password | `file:upload` |
| `GET` | `/api/vault/files` | List my vault files | `file:upload` |
| `POST` | `/api/vault/files` | Upload a file straight into the vault | `file:upload` |
| `PATCH` | `/api/vault/files/{file_id}` | Rename a vault file | `file:upload` |
| `DELETE` | `/api/vault/files/{file_id}` | Delete a vault file permanently | `file:upload` |
| `GET` | `/api/vault/files/{file_id}/download` | Download a vault file | `file:upload` |
| `POST` | `/api/vault/files/{file_id}/move-out` | Move a vault file back to My Files | `file:upload` |
| `GET` | `/api/vault/files/{file_id}/preview` | Show a vault file in the browser | `file:upload` |
| `POST` | `/api/vault/import/{file_id}` | Move a file from My Files into the vault (its shares are removed) | `file:upload` |
| `POST` | `/api/vault/password` | Change vault password | `file:upload` |
| `POST` | `/api/vault/reset` | Forgot the vault password: delete the vault and all its files | `file:upload` |

## Sharing

Share links and direct shares: create (one file, several files or a folder), list, edit, revoke, access history, and recipient preview/download.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/files/{file_id}/shares` | All shares of one of my files, with their status | `file:read` |
| `POST` | `/api/files/{file_id}/shares` | Share a file: secret link or a registered person (requires share:create) | `share:create` |
| `POST` | `/api/folders/{folder_id}/shares` | Share every file in one of my folders (sub-folders included) with the same settings | `share:create` |
| `POST` | `/api/shares/bulk` | Share several of my files at once (same settings; one link per file) | `share:create` |
| `GET` | `/api/shares/received` | Shared with me | `file:read` |
| `GET` | `/api/shares/sent` | Shared by me | `file:read` |
| `PATCH` | `/api/shares/{share_id}` | Edit a share: permission, expiry or download limit – the link stays the same | `share:create` |
| `DELETE` | `/api/shares/{share_id}` | Revoke a share – the link or access stops working immediately | Signed in |
| `GET` | `/api/shares/{share_id}/access` | Access history of one of my shares: who opened, viewed or downloaded it, and when | Signed in |
| `GET` | `/api/shares/{share_id}/download` | Download a file shared with me (download permission) | `file:read` |
| `GET` | `/api/shares/{share_id}/preview` | Preview a file shared with me | `file:read` |

## Public share links

Used by link visitors without an account. Rate-limited per IP. Password-protected links need the `X-Share-Password` header (missing or wrong → `403`, 5 wrong → `429` for 15 minutes).

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/s/{token}` | Shared file details | Public |
| `GET` | `/api/s/{token}/download` | Download the shared file (download permission) | Public |
| `GET` | `/api/s/{token}/preview` | View the shared file in the browser | Public |

## My analytics

The signed-in user's File Analytics and activity log.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/activity/me` | My own activity log | Signed in |
| `GET` | `/api/analytics/me` | File Analytics for my files (default: last 30 days) | `file:read` |

## Notifications

In-app notifications, email preferences and the real-time stream (Server-Sent Events).

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/notifications` | My notifications, newest first | Signed in |
| `GET` | `/api/notifications/admin/stats` | Notification Management: totals, email delivery, recent deliveries (no message text) | `audit:read` |
| `GET` | `/api/notifications/preferences` | Which notifications I get by email | Signed in |
| `PUT` | `/api/notifications/preferences` | Turn email per type on or off | Signed in |
| `POST` | `/api/notifications/read-all` | Mark all my notifications as read | Signed in |
| `GET` | `/api/notifications/stream` | Live notifications (Server-Sent Events) – read with fetch + Authorization header | Signed in |
| `GET` | `/api/notifications/unread-count` | Number of unread notifications | Signed in |
| `POST` | `/api/notifications/{notification_id}/read` | Mark one as read | Signed in |

## Admin – users

Account management. Admins can never open users' files.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/admin/users` | List all users (requires user:read – admins only) | `user:read` |
| `PATCH` | `/api/admin/users/{user_id}` | Change a user's role and/or enable or disable the account (requires user:manage) | `user:manage` |
| `DELETE` | `/api/admin/users/{user_id}` | Delete an account inactive for 30+ days, with all its files (user:delete_inactive) | `user:delete_inactive` |
| `POST` | `/api/admin/users/{user_id}/unlock` | Unlock an account locked after too many failed logins (requires user:manage) | `user:manage` |

## Admin – security dashboard

Security overview, logins, security events and the activity audit export.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/admin/audit` | Audit log of every user's activity, with search and filters (audit:read) | `audit:read` |
| `GET` | `/api/admin/audit/export` | Download the audit log as CSV – same filters, max 10,000 rows (audit:read) | `audit:read` |
| `GET` | `/api/admin/overview` | Admin Dashboard: users, storage per account, sharing, activity, keys (user:read) | `user:read` |
| `GET` | `/api/admin/security/events` | Security events, newest first (audit:read) | `audit:read` |
| `GET` | `/api/admin/security/logins` | Login history of all users (audit:read) | `audit:read` |
| `GET` | `/api/admin/security/overview` | Security Dashboard: metrics, charts, recent logins and events (audit:read) | `audit:read` |

## Admin – activity monitoring

Every recorded action, with filters, a summary and a live stream.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/activity-monitoring/activities` | Activity feed, newest first | `audit:read` |
| `GET` | `/api/activity-monitoring/stream` | Live activity feed (Server-Sent Events, file names removed) | `audit:read` |
| `GET` | `/api/activity-monitoring/summary` | Activity counts by type | `audit:read` |
| `GET` | `/api/activity-monitoring/types` | Activity types used for filtering | `audit:read` |

## Admin – audit logs

The hash-chained, tamper-evident audit log: filters, verification and CSV export.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/audit-logs` | All audit logs, newest first | `audit:read` |
| `GET` | `/api/audit-logs/export` | Download filtered audit logs as CSV (max 10,000 rows) | `audit:read` |
| `GET` | `/api/audit-logs/file/{file_id}` | Everything that happened to one file (by file ID – names are never shown to admins) | `audit:read` |
| `GET` | `/api/audit-logs/filter` | Filter by user, activity type, file ID, status and date range | `audit:read` |
| `GET` | `/api/audit-logs/user/{user_id}` | One user's audit logs | `audit:read` |
| `GET` | `/api/audit-logs/verify` | Re-compute every hash: has any audit entry been changed or deleted? | `audit:read` |

## Admin – security monitoring

Security events and suspicious-activity alerts with the open → acknowledged → resolved workflow, and the detection rules.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/security-monitoring/events` | Security events / alerts – filter by user, type, severity, status and dates | `audit:read` |
| `GET` | `/api/security-monitoring/events/{alert_id}` | One alert | `audit:read` |
| `PATCH` | `/api/security-monitoring/events/{alert_id}` | Acknowledge, resolve (with a note) or reopen an alert | `audit:read` |
| `GET` | `/api/security-monitoring/rules` | Detection rules and their current thresholds | `audit:read` |
| `GET` | `/api/security-monitoring/summary` | Totals for the Security Monitoring section (default: last 30 days) | `audit:read` |

## Admin – reports

Upload, download, sharing, per-user and security reports (`format=csv` for export).

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/reports/downloads` | File download report | `audit:read` |
| `GET` | `/api/reports/security` | Security report | `audit:read` |
| `GET` | `/api/reports/sharing` | File sharing report | `audit:read` |
| `GET` | `/api/reports/uploads` | File upload report | `audit:read` |
| `GET` | `/api/reports/users/{account_id}` | One user's activity report | `audit:read` |

## Admin – storage analytics

Storage, file, download and sharing statistics across all accounts – sizes and counts only.

| Method | Path | What it does | Access |
|---|---|---|---|
| `GET` | `/api/analytics/downloads` | Download statistics | `audit:read` |
| `GET` | `/api/analytics/files` | File statistics (uploads by date) | `audit:read` |
| `GET` | `/api/analytics/sharing` | Sharing statistics | `audit:read` |
| `GET` | `/api/analytics/storage` | Total storage usage | `audit:read` |
| `GET` | `/api/analytics/users/storage` | Storage used by each user | `audit:read` |
