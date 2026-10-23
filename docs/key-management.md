# TrustShare – Encryption & Key Management (Milestone 2)

How TrustShare protects stored files: which keys exist, where they live, who can use them, and how they
are rotated and recovered. Companion to [architecture.md §8](architecture.md#8-milestone-2--encryption-storage-and-sharing)
and [database.md](database.md).

---

## 1. Goals

| Goal | How |
|---|---|
| Files are unreadable in storage | Every file is encrypted with **AES-256-GCM** before it leaves the backend. |
| A stolen storage bucket is useless | The bucket holds only ciphertext; keys are elsewhere. |
| A stolen database is useless | Databases hold only **wrapped** (encrypted) file keys; the master key is not in any database. |
| Tampering is detected | GCM authentication tags + associated data bind each chunk to its file and position. |
| Users never handle keys | Keys never appear in API responses, logs, URLs or the browser. |
| Keys can be rotated | Master keys are versioned; rotation re-wraps file keys without re-encrypting files. |

---

## 2. Key hierarchy (envelope encryption)

```
Master keys (KEKs)  – versioned, 256-bit, in the server's environment (.env / secret manager)
   └── wraps ──►  File key (DEK) – random 256-bit, one per file, stored ONLY in wrapped form
                     └── encrypts ──►  the file's bytes (chunked AES-256-GCM) in object storage
```

| Key | Purpose | Size | Where it lives | Who can use it |
|---|---|---|---|---|
| **KEK** (key-encryption key / master key) | Wraps and unwraps DEKs | 256 bits | `MASTER_KEYS` environment variable of the backend container (production: AWS KMS / secret manager) | Only the backend's `Keyring` |
| **DEK** (data-encryption key / file key) | Encrypts one file | 256 bits | PostgreSQL `file_keys.wrapped_key` – **encrypted with a KEK** | Only `EncryptionService`, in memory, for one request |
| Fernet key (`MFA_ENCRYPTION_KEY`) | Encrypts TOTP secrets (Milestone 1) | – | Environment | `MfaService` |

**Why envelope encryption?** One key per file limits damage (a leaked DEK exposes one file, not all), and
rotating the master key only means re-wrapping small 32-byte DEKs instead of re-encrypting gigabytes.

**Separation of storage:** ciphertext → object storage (RustFS / AWS S3) · file metadata → MongoDB ·
wrapped DEKs → PostgreSQL · KEKs → environment. An attacker needs **all four** to read a file.

---

## 3. Algorithms and parameters

| Item | Choice | Notes |
|---|---|---|
| Cipher | **AES-256-GCM** (`cryptography` library, `AESGCM`) | Authenticated encryption: confidentiality **and** integrity. No home-made crypto. |
| DEK generation | `AESGCM.generate_key(bit_length=256)` (OS CSPRNG) | Fresh for every upload. |
| File format | Chunked "STREAM" construction, 1 MiB plaintext chunks | Constant memory; any chunk can be checked independently. |
| Chunk nonce (96 bits) | 7-byte random prefix ‖ 4-byte chunk counter ‖ 1-byte last-chunk flag | Never repeats for a given DEK (counter), so nonce reuse is impossible. |
| Associated data (AAD) | file id ‖ chunk index | Swapping chunks between files, reordering or dropping chunks fails authentication. |
| Truncation protection | Last chunk is marked by the nonce flag | A file cut short is rejected (no "last" chunk). |
| DEK wrapping | AES-256-GCM with the active KEK, random 96-bit nonce, AAD = file id ‖ KEK version | A wrapped key can't be moved to another file. |
| Integrity cross-check | SHA-256 of the plaintext (Milestone 1) kept in metadata | Optional extra check after decryption. |

**Encrypted object layout**
```
header:  "TSE1" (magic) | version (1 byte) | chunk size (4 bytes) | nonce prefix (7 bytes)
chunks:  ciphertext_0 + tag_0 | ciphertext_1 + tag_1 | … | ciphertext_n + tag_n   (each tag 16 bytes)
```

---

## 4. Key lifecycle

### 4.1 Generation
On upload, after validation (type, size, quota, magic bytes): the backend generates a new DEK, encrypts
the file chunk by chunk while streaming it to object storage, wraps the DEK with the **active** KEK and
stores the wrapped key in `file_keys` together with the KEK **version** used.

### 4.2 Storage
- `file_keys(file_id, wrapped_key, key_version, algorithm, created_at, rotated_at)` in PostgreSQL.
- The raw DEK exists only in backend memory during the request and is discarded afterwards.
- KEKs are loaded once from the environment into the `Keyring`; they are never written to a database,
  a log or an API response.

### 4.3 Use (retrieval)
Only after authentication **and** authorization (owner, valid direct share, or valid share link):
load `file_keys` row → unwrap the DEK with the KEK of the stored version → stream the object from storage →
decrypt and verify each chunk → stream plaintext to the client. If any tag fails, the request ends with
an error and **no unverified plaintext is returned**; the event is logged as a security event.

### 4.4 Rotation
- **Master key rotation (planned or after suspected exposure):**
  1. `python -m app.scripts.rotate_keys --new-key` prints the next version with a fresh random KEK
     (the only time a key is ever printed). Append it to `MASTER_KEYS` (`1:<old>,2:<new>`) and store a
     separate backup.
  2. Set `ACTIVE_MASTER_KEY_VERSION=2` and restart the backend – new uploads use `v2`, old files still
     open with `v1`.
  3. Run `python -m app.scripts.rotate_keys` – it unwraps every DEK still on an old version and re-wraps it
     with `v2` (batches of 100, one transaction each; safe to stop and re-run). A key whose KEK is
     missing is reported and left unchanged. The run is recorded in the activity log (`key.rotate`).
  4. `python -m app.scripts.rotate_keys --status` shows how many keys use each version; when no key uses
     `v1` any more, remove `v1` from `MASTER_KEYS` and restart.
- Files stay decryptable throughout: every row records which KEK version wrapped it, and old versions
  remain available until re-wrapping is finished.
- **DEK rotation** (re-encrypting a file with a new DEK) is not needed routinely; it is done by
  re-uploading/re-encrypting a file if a single DEK were ever exposed.
- Suggested policy: rotate the master key every 90 days and immediately after any suspected leak.

### 4.5 Deletion
"Delete forever" removes the object from storage **and** its `file_keys` row. Without the DEK the
ciphertext is permanently unreadable even if a storage backup still contains it ("crypto-shredding").

### 4.6 Backup and recovery
- **Master keys must be backed up separately** from database and storage backups (e.g. in a password
  manager / secret manager with restricted access). Losing every copy of a KEK makes the files it
  protects unrecoverable – by design.
- Database backups contain only wrapped keys; storage backups contain only ciphertext.
- Recovery = restore PostgreSQL (wrapped keys) + object storage + provide the same `MASTER_KEYS`.

---

## 5. Access to keys

| Component | Can see raw DEK? | Can see KEK? |
|---|---|---|
| `EncryptionService` / `Keyring` (backend) | Yes, in memory, per request | Yes (loaded from env) |
| Routes, other services | No – they call the encryption service | No |
| API responses, logs, activity logs | **Never** (tests verify this) | **Never** |
| Browser / users / admins | **Never** | **Never** |
| Object storage (RustFS / S3) | No – only ciphertext | No |
| PostgreSQL / MongoDB | No – only wrapped keys / metadata | No |

In production the KEK would live in a key-management service (e.g. **AWS KMS**) so that even the backend
host never sees the master key – the `Keyring` is the single place to swap in such a provider.

---

## 6. Error handling

| Situation | Behaviour |
|---|---|
| Wrong key / missing KEK version | 500 "File could not be decrypted", security event logged; no plaintext sent. |
| Tampered or corrupted object | Same – the GCM tag check fails before the chunk is released. |
| Missing `file_keys` row | 500 + security event (data inconsistency); file treated as unavailable. |
| Decryption error mid-stream | The connection is closed; already-verified chunks only were sent. |

Plaintext is never written to disk or logs by the backend; temporary upload files are deleted after
encryption.
