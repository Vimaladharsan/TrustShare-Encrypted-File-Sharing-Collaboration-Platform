# Performance and responsiveness

Measured on the **live deployment** (https://trustshare-vimal.centralindia.cloudapp.azure.com) on
**19 November 2026**, as part of Milestone 4. It covers the performance metrics named in the project
brief: encryption speed, upload / download time, API response time, concurrent users, detection
accuracy, and UI responsiveness.

## Summary

| Brief metric | Result |
|---|---|
| Encryption speed | AES-256-GCM **≈ 860–1,150 MB/s** encrypt, **≈ 385–580 MB/s** decrypt on the server – a 25 MB file (the upload maximum) encrypts in **25 ms** |
| Upload / download time | Inside Azure: 10 MB uploads in **0.6 s** and downloads in **0.3 s**. From a home connection the time is set by the user's internet speed |
| API response time | Server processing **≈ 5 ms** median for most requests; **≈ 70–85 ms** median as seen by a user in India (mostly network distance) |
| Concurrent users | **50 active users** served at 52 requests/s with **0 errors**; 100 users still 0 errors but slower – the limit of the free 1 GB machine |
| Detection accuracy | **7 / 7 attacks detected, 0 / 8 false alarms** at the exact rule limits |
| UI responsiveness | First visit **≈ 250 KB** compressed; pages appear in **≈ 0.4–0.6 s** (median); no sideways scrolling on any page at phone, tablet or desktop width; 0 console errors |

## Test environment

| | |
|---|---|
| Server | Azure VM **Standard B2ats v2** (free tier): 2 burstable vCPUs, ≈ 0.9 GB RAM + 4 GB swap, Central India |
| Software | Production stack from `docker-compose.prod.yml`: Caddy → FastAPI (**one** worker process, chosen for the small machine) → PostgreSQL, MongoDB, Redis; files in Azure Blob Storage |
| Users' side | A laptop on home broadband in India (≈ 2–5 Mbit/s upload, ≈ 50–90 ms round trip to the server) |
| Data | Test accounts only; test files deleted afterwards |
| Idle memory | ≈ 360 MB used by the whole stack (MongoDB ≈ 260 MB, the others ≈ 5–40 MB each) |

To separate the **server's** speed from the **network's**, upload and load tests were run twice: from
the laptop (what a real user experiences) and from inside the Azure VM (what the server can do).

## 1. Encryption speed

Run inside the live backend container with the real encryption code (`encrypt_file`,
`decrypt_bytes` in `app/services/encryption_service.py`; 1 MiB AES-256-GCM chunks, median of 5 runs):

| File size | Encrypt | Decrypt + verify | Size overhead |
|---|---|---|---|
| 1 MB | 1 ms (≈ 1,150 MB/s) | 2 ms (≈ 580 MB/s) | 32 bytes |
| 10 MB | 12 ms (≈ 860 MB/s) | 18 ms (≈ 540 MB/s) | 176 bytes |
| 25 MB | 25 ms (≈ 1,020 MB/s) | 65 ms (≈ 385 MB/s) | 416 bytes |

| Other cryptographic step | Time |
|---|---|
| Create a file key and wrap / unwrap it with the master key (envelope encryption) | 0.016 ms per file |
| bcrypt password hash (cost 12) – deliberately slow to resist guessing | ≈ 330 ms |

**Meaning:** encryption is never the bottleneck – it adds about 1 ms per megabyte, far less than
the time to send a megabyte over the internet. The overhead is a 16-byte header plus a 16-byte
authentication tag per 1 MiB chunk. bcrypt is slow on purpose: it is what makes stolen password
hashes expensive to crack.

## 2. API response time

**Server processing time** (from the backend's own request log during the tests, i.e. without the
network):

| Request | Median | 95th percentile |
|---|---|---|
| `GET /api/files` (list) | 7 ms | – (see load test) |
| `GET /api/files/usage` | 6 ms | 23 ms |
| `GET /api/folders` | 6 ms | 23 ms |
| `GET /api/files/{id}` | 5 ms | 18 ms |
| `GET /api/users/me` | 4 ms | 15 ms |
| `GET /api/analytics/me` | 14 ms | 16 ms |
| `GET /api/s/{token}` (public link) | 6 ms | 11 ms |
| `GET /api/files/{id}/download` (small file, fetched from Azure + decrypted) | 18 ms | 160 ms |
| `POST /api/auth/login` | ≈ 600 ms | – (bcrypt, on purpose) |

**As seen by a user** (from the laptop in India, 25 requests each on a warm connection):

| Request | Median | 95th percentile |
|---|---|---|
| `GET /api/health` | 74 ms | 98 ms |
| `GET /api/users/me` | 77 ms | 96 ms |
| `GET /api/files` (list) | 79 ms | 96 ms |
| `GET /api/files?q=` (search) | 123 ms | 357 ms |
| `GET /api/folders` | 73 ms | 99 ms |
| `GET /api/files/usage` | 69 ms | 100 ms |
| `GET /api/files/{id}` | 77 ms | 105 ms |
| `GET /api/files/{id}/download` (small file) | 83 ms | 125 ms |
| `GET /api/analytics/me` | 82 ms | 301 ms |
| `GET /api/notifications/unread-count` | 77 ms | 131 ms |
| `GET /api/s/{token}` (public link) | 78 ms | 91 ms |

**Meaning:** the network round trip alone is ≈ 50–90 ms, so nearly all of what a user waits for is
distance, not processing. Every common request stays well under the 200 ms target in the
[requirements](requirements.md).

## 3. Upload and download time

Each file is checked (type, content, size, quota), hashed (SHA-256), encrypted with its own key and
stored in Azure Blob Storage; a download fetches, decrypts and verifies it. Downloads were compared
byte for byte with the original.

| File size | Upload – inside Azure | Download – inside Azure | Upload – home broadband | Download – home broadband |
|---|---|---|---|---|
| 1 MB | 0.67 s | 0.25 s | 4.1 s | 0.7 s |
| 5 MB | 0.52 s | 0.23 s | 8.6 s | 2.6 s |
| 10 MB | 0.57 s | 0.26 s | 16.9 s | 2.6 s |
| 24 MB | 7.9 s | 2.3 s | – | – |

**Meaning:** inside Azure a 10 MB file takes well under a second each way, including encryption and
the trip to Blob Storage. From home, uploads run at the connection's upload speed (≈ 2–5 Mbit/s here
– the same file would upload just as slowly to Google Drive). The 24 MB case is slower because the
small VM uses swap memory under a large upload; files are streamed in chunks, so memory never holds
the whole file.

## 4. Concurrent users

Simulated users signed in and repeatedly opened their file list, folders, storage meter, file
details, notifications and downloads, with **0.5 s pause** between clicks (a real person clicks far
less often). Each level ran for 30 s.

**From inside Azure** (the load generator ran on the same small VM, so these numbers are on the
conservative side):

| Simultaneous active users | Requests per second | Median response | 95th percentile | Errors |
|---|---|---|---|---|
| 10 | 10.8 | 27 ms | 1.3 s | 0 |
| 25 | 27.9 | 19 ms | 2.8 s | 0 |
| 50 | 51.6 | 99 ms | 3.0 s | 0 |
| 100 | 31.5 | 1.7 s | 8.7 s | 0 |

**From the laptop** (home broadband): 10 users – median 113 ms, 0 errors; 25 users – median 565 ms,
0 errors.

**Meaning:** the free machine comfortably serves about **50 users clicking at the same time** (which
corresponds to several hundred registered users, since only a fraction are active at any moment) and
**never returned an error**, even at 100. Beyond 50 the single worker process on 2 burstable vCPUs
becomes the limit, so responses slow down instead of failing. Scaling is a configuration change:
a larger VM with `WEB_WORKERS=2` or more (all shared state is already in Redis, so workers can be
added freely).

## 5. Detection accuracy

Every rule was tested exactly **at its limit** on the local copy of the system (so the live admin
console was not flooded): one step below the limit must stay quiet, one step above must alert. A
normal user session must raise no alert at all.

| Scenario | Expected | Result |
|---|---|---|
| Normal session: upload, folder, rename, 8 downloads, share link, 3 link downloads, trash and restore | no alert | ✅ none |
| 5 wrong passwords for one account | no rule alert (only the lockout notice) | ✅ `multiple_failed_logins`, `account_locked` – no rule alert |
| 6th wrong attempt | `repeated_failed_logins` | ✅ raised |
| 4 attempts to open another user's file | no alert | ✅ none |
| 5th attempt | `repeated_unauthorized_access` | ✅ raised |
| 20 downloads within seconds | no alert | ✅ none |
| 21st download | `excessive_downloads` | ✅ raised |
| 2 tries of a revoked link | no alert | ✅ none |
| 3rd try | `revoked_link_abuse` | ✅ raised |
| 2 tries of an expired link | no alert | ✅ none |
| 3rd try | `expired_link_abuse` | ✅ raised |
| Upload of a real PDF | no alert | ✅ none |
| Upload of a program renamed to `.pdf` | `file_threat` | ✅ raised |
| Same browser refreshes twice within the grace window (page reload) | no alert | ✅ none |
| Old refresh token used from another device | `token_reuse` | ✅ raised |

| | |
|---|---|
| Attacks detected (true positives) | **7 / 7** |
| Normal behaviour wrongly flagged (false positives) | **0 / 8** |
| Precision · Recall | **100 % · 100 %** at the configured limits |

During the [live security test](security-testing.md) every attack type also raised its alert on the
production server. The detection is rule-based, so it is exact at the limits; the limits are
configurable in `.env` (`DETECT_*`) to balance sensitivity against noise.

## 6. UI responsiveness and optimisation

**Page weight** (measured with `curl` on the live site):

| What | Compressed size |
|---|---|
| `index.html` | 0.5 KB |
| Main JavaScript (`index-*.js`, 599 KB uncompressed) | 189 KB (zstd / gzip) |
| Styles (`index-*.css`, 88 KB uncompressed) | 16 KB |
| Font (Inter, Latin) | 48 KB |
| **First visit total** | **≈ 250 KB** |
| Charts (loaded only when an analytics page is opened) | 119 KB |

**Page load in a real browser** (Microsoft Edge driven by Playwright, live site, signed-in test user,
11 pages – landing, login, public share page, dashboard, My Files, Shared by me, analytics, security,
settings, storage, activity):

| Device size | First visit – first content | Later pages – median first content | Sideways scrolling | Console errors |
|---|---|---|---|---|
| Phone (375 × 812, touch) | 2.3 s | 0.6 s | none on any page | 0 |
| Tablet (768 × 1024) | 1.2 s | 0.5 s | none on any page | 0 |
| Desktop (1366 × 768) | 1.0 s | 0.5 s | none on any page | 0 |

**Optimisations in place:**

- **Compression:** Caddy serves zstd / gzip – the main script shrinks from 599 KB to 189 KB.
- **Caching:** build files have content hashes in their names and are cached for a year
  (`immutable`); `index.html` is always revalidated, so a new release is picked up immediately.
- **Code splitting:** the charts library and admin pages are loaded only when needed
  (`React.lazy`).
- **Streaming:** uploads, encryption, decryption and downloads work in 1 MiB chunks – memory use does
  not grow with file size.
- **Database indexes** on every lookup column ([database design](database.md)).
- **Small-machine tuning:** MongoDB cache 0.25 GB, PostgreSQL `shared_buffers` 64 MB, Redis capped at
  96 MB, one worker process – the whole stack idles at ≈ 360 MB.
- **Responsive layout:** the sidebar becomes a slide-in drawer on phones, less important table
  columns (type, date) hide on narrow screens, wide tables scroll inside their own card instead of
  the page, and dialogs fit the screen; checked at 375, 768 and 1366 px.

## How to repeat

| Metric | How |
|---|---|
| Encryption speed | In the backend container, time `encrypt_file` / `decrypt_bytes` from `app/services/encryption_service.py` on random data |
| API time (server side) | Every request is logged with its duration: `docker compose -f docker-compose.prod.yml logs backend \| grep app.request` |
| API time / transfers (user side) | Time requests with any HTTP client against the live URL using a test account |
| Concurrent users | Many async clients with a short pause between requests, run from inside the VM to exclude the home network |
| Detection accuracy | On a local stack: for each rule, repeat the action up to the limit (no alert) and once more (alert); read `security_events` |
| Page weight / load | `curl --compressed` for sizes; a browser's Performance panel or Playwright for timings at phone / tablet / desktop sizes |
