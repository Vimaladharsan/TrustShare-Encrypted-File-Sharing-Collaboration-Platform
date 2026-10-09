# TrustShare – Database Design

Three stores, each used for what it does best (see [architecture.md](architecture.md#why-three-databases)).

| Store | Data |
|---|---|
| PostgreSQL | Identity & authorisation: users, roles, permissions, OAuth links, MFA backup codes. **(M2)** shares. |
| MongoDB | File metadata, folders, activity / audit logs. |
| Redis | Short-lived security state: refresh sessions, one-time tokens, rate limits, lockouts. |

### Data placement rationale (read this before the viva)

The M1 brief is slightly inconsistent: its intro says file details go in PostgreSQL, while Step 4, the expected outcomes and the **graded checklist** say file metadata goes in **MongoDB**. The full brief's M2 workflow says "metadata **and permissions** in PostgreSQL".

TrustShare follows the graded checklist and resolves the rest by data type:

- **Who may do what** (accounts, roles, permissions, and from M2 share grants) → **PostgreSQL**, because authorisation needs foreign keys, uniqueness and transactions.
- **Describing files** (name, size, type, hash, folder, version, later encryption info) → **MongoDB**, because the shape varies per file type and evolves each milestone without migrations.
- The two are joined by IDs: Mongo documents store the PostgreSQL `user_id` (UUID) as `owner_id`; M2 share rows store the Mongo `file_id`.

The cross-database link is safe because every write path goes through one service (e.g. `FileService`), and the user ID is immutable.

---

## 1. PostgreSQL (relational)

### 1.1 ER diagram

```mermaid
erDiagram
    ROLES ||--o{ USERS : "has"
    ROLES ||--o{ ROLE_PERMISSIONS : "grants"
    PERMISSIONS ||--o{ ROLE_PERMISSIONS : "granted by"
    USERS ||--o{ OAUTH_ACCOUNTS : "links"
    USERS ||--o{ MFA_BACKUP_CODES : "owns"

    ROLES {
        smallint id PK
        varchar name UK "admin | user | guest"
        varchar description
    }
    PERMISSIONS {
        smallint id PK
        varchar code UK "e.g. file:upload"
        varchar description
    }
    ROLE_PERMISSIONS {
        smallint role_id PK,FK
        smallint permission_id PK,FK
    }
    USERS {
        uuid id PK
        citext email UK
        varchar full_name
        varchar password_hash "nullable (Google-only accounts)"
        smallint role_id FK
        boolean is_active
        boolean is_email_verified
        boolean mfa_enabled
        text mfa_secret_encrypted "Fernet-encrypted TOTP secret"
        bigint storage_quota_bytes
        timestamptz password_changed_at
        timestamptz last_login_at
        timestamptz created_at
        timestamptz updated_at
    }
    OAUTH_ACCOUNTS {
        uuid id PK
        uuid user_id FK
        varchar provider "google"
        varchar provider_user_id "Google 'sub'"
        citext email
        timestamptz created_at
    }
    MFA_BACKUP_CODES {
        uuid id PK
        uuid user_id FK
        varchar code_hash "bcrypt of one-time code"
        timestamptz used_at "null = unused"
        timestamptz created_at
    }
```

### 1.2 Tables

**`roles`** – seeded by migration.

| id | name | description |
|---|---|---|
| 1 | admin | Full platform administration |
| 2 | user | Standard member, manages own files |
| 3 | guest | Read-only access |

**`permissions`** – seeded by migration: `file:read`, `file:upload`, `file:update`, `file:delete`, `folder:manage`, `file:read_all`, `user:read`, `user:manage`, `audit:read`, `share:create` (M2).

**`role_permissions`** – mapping from the permission matrix in [requirements.md](requirements.md#3-permission-matrix).

**`users`**

| Column | Type | Constraints / notes |
|---|---|---|
| id | `uuid` | PK, generated server-side (`uuid4`). UUIDs don't reveal how many users exist and can't be guessed. |
| email | `citext` | `UNIQUE NOT NULL` – case-insensitive, so `A@x.com` = `a@x.com`. |
| full_name | `varchar(100)` | `NOT NULL` |
| password_hash | `varchar(255)` | bcrypt hash; `NULL` for accounts created only through Google. |
| role_id | `smallint` | FK → roles, default `2` (user). Not settable by the client at sign-up. |
| is_active | `boolean` | default `true`; admin can deactivate. |
| is_email_verified | `boolean` | default `false`; `true` for Google sign-ups (Google verified it). |
| mfa_enabled | `boolean` | default `false` |
| mfa_secret_encrypted | `text` | TOTP secret, encrypted with a server key (Fernet). Even a DB dump does not reveal it. |
| storage_quota_bytes | `bigint` | default 1 GB (from env). Usage is computed from MongoDB, not stored twice. |
| password_changed_at | `timestamptz` | Access tokens issued before this time are rejected. |
| last_login_at, created_at, updated_at | `timestamptz` | |

Indexes: `UNIQUE(email)`, `INDEX(role_id)`.

**`oauth_accounts`** – `UNIQUE(provider, provider_user_id)`, `INDEX(user_id)`, `ON DELETE CASCADE`.

**`mfa_backup_codes`** – 10 rows per user when MFA is enabled; regenerating deletes old rows. `INDEX(user_id)`, `ON DELETE CASCADE`.

**Planned (M2):** `shares` (id, file_id, owner_id, token_hash, permission view/download, expires_at, max_downloads, download_count, password_hash, revoked_at), `file_permissions` (file_id, user_id, access level).

Migrations are managed with **Alembic** (`backend/alembic/versions`).

---

## 2. MongoDB (documents)

Database: `trustshare`. Collections: `files`, `folders`, `activity_logs`.

### 2.1 `files`

```json
{
  "_id": ObjectId("6718c2f0a1b2c3d4e5f60789"),
  "owner_id": "6f1c2a3e-8b4d-4e2f-9a1b-2c3d4e5f6a7b",
  "folder_id": ObjectId("6718c2a0a1b2c3d4e5f60111"),
  "original_name": "Q3 Report.pdf",
  "name_lower": "q3 report.pdf",
  "extension": "pdf",
  "mime_type": "application/pdf",
  "category": "document",
  "size_bytes": 482133,
  "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "storage_backend": "local",
  "storage_key": "6f1c2a3e-.../a8c4e9f2-3b1d-4c7e-9f00-1e2d3c4b5a69",
  "version": 1,
  "status": "active",
  "trashed_at": null,
  "encryption": null,
  "created_at": ISODate("2026-10-12T09:15:22Z"),
  "updated_at": ISODate("2026-10-12T09:15:22Z")
}
```

| Field | Notes |
|---|---|
| owner_id | PostgreSQL `users.id` (string UUID). |
| folder_id | `null` = root ("My Files"). |
| original_name | Sanitised display name (control chars, `/`, `\` removed, max 255). Never used as a path. |
| name_lower | For case-insensitive search & sorting. |
| category | `document` (pdf, docx), `spreadsheet` (xlsx, csv), `presentation` (pptx), `image` (png, jpg), `text` (txt). Drives filters and icons. |
| sha256 | Integrity + duplicate detection. In M2 also proves the decrypted file matches the original. |
| storage_key | Random server-generated path inside the storage backend. |
| status | `active` or `trashed`. Permanent delete removes the document and the stored file. |
| encryption | `null` in M1. **(M2)** `{ "algorithm": "AES-256-GCM", "wrapped_key": "...", "nonce": "...", "key_version": 1 }` – added without any migration. |

Indexes:

| Index | Purpose |
|---|---|
| `{ owner_id: 1, folder_id: 1, status: 1, name_lower: 1 }` | Folder listing sorted by name (the most common query). |
| `{ owner_id: 1, status: 1, created_at: -1 }` | "Recent" view, date sort, date filter. |
| `{ owner_id: 1, sha256: 1 }` | Duplicate detection. |
| `{ owner_id: 1, category: 1 }` | Category filter. |
| text index on `original_name` | Search box. |

Storage usage per user: `aggregate([{ $match: { owner_id } }, { $group: { _id: null, used: { $sum: "$size_bytes" } } }])`.

### 2.2 `folders`

```json
{
  "_id": ObjectId("6718c2a0a1b2c3d4e5f60111"),
  "owner_id": "6f1c2a3e-8b4d-4e2f-9a1b-2c3d4e5f6a7b",
  "name": "Finance",
  "name_lower": "finance",
  "parent_id": null,
  "ancestors": [],
  "status": "active",
  "trashed_at": null,
  "created_at": ISODate("2026-10-12T09:10:00Z"),
  "updated_at": ISODate("2026-10-12T09:10:00Z")
}
```

`ancestors` holds the ordered list of parent folder IDs (materialised path). Benefits: breadcrumbs in **one** query, and moving/trashing a folder finds all descendants with `{ ancestors: folderId }`. A folder cannot be moved into itself or its own descendant.

Indexes: unique `{ owner_id, parent_id, name_lower }` with partial filter `status: "active"` (no two active folders with the same name in one place); `{ ancestors: 1 }`.

### 2.3 `activity_logs` (append-only audit trail)

```json
{
  "_id": ObjectId("6718c3b1a1b2c3d4e5f60999"),
  "user_id": "6f1c2a3e-8b4d-4e2f-9a1b-2c3d4e5f6a7b",
  "actor_email": "vimal@example.com",
  "action": "file.upload",
  "resource_type": "file",
  "resource_id": "6718c2f0a1b2c3d4e5f60789",
  "status": "success",
  "ip_address": "172.18.0.1",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
  "request_id": "b1f2c3d4",
  "details": { "file_name": "Q3 Report.pdf", "size_bytes": 482133 },
  "created_at": ISODate("2026-10-12T09:15:22Z")
}
```

Action names: `auth.register`, `auth.verify_email`, `auth.login.success`, `auth.login.failed`, `auth.login.locked`, `auth.logout`, `auth.logout_all`, `auth.refresh_reuse_detected`, `auth.password_reset_requested`, `auth.password_reset`, `auth.password_changed`, `auth.mfa_enabled`, `auth.mfa_disabled`, `auth.oauth_login`, `file.upload`, `file.upload_rejected`, `file.download`, `file.preview`, `file.rename`, `file.move`, `file.trash`, `file.restore`, `file.delete`, `folder.create`, `folder.rename`, `folder.move`, `folder.trash`, `admin.user_role_changed`, `admin.user_deactivated`, `admin.user_unlocked`.

Rules: the API has **no** update or delete endpoint for this collection; failed actions are logged too (they are what M3 suspicious-activity detection looks at).

Indexes: `{ user_id: 1, created_at: -1 }`, `{ action: 1, created_at: -1 }`, `{ ip_address: 1, created_at: -1 }`.

---

## 3. Redis (key-value, auto-expiring)

All one-time tokens are stored **hashed** (`sha256(token)`) – if Redis is dumped, the tokens in emails still can't be reconstructed.

| Key pattern | Type | Value | TTL | Used for |
|---|---|---|---|---|
| `refresh:{jti}` | hash | `user_id, family_id, ip, user_agent, created_at` | 7 days | Active refresh session. Deleted on use (rotation) or logout. |
| `user_sessions:{user_id}` | set | refresh `jti`s | 7 days (renewed) | Logout-all, "active sessions" count. |
| `access_denylist:{jti}` | string | `1` | remaining access-token life (≤ 15 min) | Access token revoked by logout before it expires. |
| `email_verify:{sha256(token)}` | string | `user_id` | 24 h | Email verification link. |
| `pwd_reset:{sha256(token)}` | string | `user_id` | 15 min | Password reset link (single use – `GETDEL`). |
| `mfa_challenge:{id}` | string | `user_id` | 5 min | Between password step and TOTP step. |
| `mfa_setup:{user_id}` | string | pending TOTP secret | 10 min | QR shown but not yet confirmed. |
| `totp_used:{user_id}:{code}` | string | `1` | 90 s | Prevents replaying the same TOTP code. |
| `oauth_state:{state}` | string | `1` | 10 min | CSRF protection for Google login. |
| `login_fail:{user_id}` | counter | failures | 15 min | 5 failures → lockout. |
| `lockout:{user_id}` | string | `1` | 15 min | Account temporarily locked. Admin "unlock" deletes it. |
| `rl:{scope}:{ip}` | counter | requests | 60 s window | Rate limiting, e.g. `rl:login`, `rl:register`, `rl:forgot`, `rl:upload`. |

Why Redis and not PostgreSQL for these: they are read on almost every request, they must disappear on time, and losing them is harmless (worst case the user logs in again). TTL makes expiry automatic – no cleanup jobs.

---

## 4. File store (`StorageBackend`)

```python
class StorageBackend(Protocol):
    async def save(self, key: str, chunks: AsyncIterator[bytes]) -> int: ...
    async def open(self, key: str) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> None: ...
```

- **M1 – `LocalStorage`:** `storage/{user_id}/{uuid}` inside a Docker volume, not inside the web root.
- **M2 – `EncryptedStorage(S3Storage)`:** wraps any backend; encrypts each file with its own AES-256-GCM key, wraps that key with the master key (envelope encryption), uploads ciphertext to S3. `FileService` code does not change.
