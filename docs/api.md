# TrustShare – API Reference

All endpoints are under `/api`. Interactive documentation (Swagger UI) is available at
http://localhost:8000/docs while the backend is running, and the machine-readable schema at
http://localhost:8000/openapi.json.

Authentication: send the access token as `Authorization: Bearer <token>`. Permissions in the
table (`audit:read`, `user:manage`, …) are checked by the backend on every request.



| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Auth | `POST /api/auth/register`, `/login`, `/mfa/verify`, `/refresh`, `/logout`, `/logout-all`, `/forgot-password`, `/reset-password`, `/verify-email`, `/verify-email/resend`; `GET /api/auth/providers`, `/google/login`, `/google/callback` |
| Profile & MFA | `GET` · `PATCH` · `DELETE /api/users/me`, `POST /api/users/me/password`, `GET /api/users/me/overview` (security score + stats), `GET /api/users/me/sessions`, `DELETE /api/users/me/sessions/{id}`, `GET /api/users/me/mfa`, `POST /api/users/me/mfa/setup`, `/enable`, `/disable`, `/backup-codes` |
| Admin | `GET /api/admin/users` (requires `user:read`), `PATCH /api/admin/users/{id}` (role, enable/disable), `POST /api/admin/users/{id}/unlock` (require `user:manage`), `DELETE /api/admin/users/{id}` (inactive 30+ days, requires `user:delete_inactive`) |
| Files | `POST /api/files` (upload), `GET /api/files`, `GET /api/files/usage`, `GET/PATCH/DELETE /api/files/{id}`, `GET /api/files/{id}/download`, `GET /api/files/{id}/preview`, `POST /api/files/{id}/trash`, `/restore`, `POST /api/files/bulk/move`, `/bulk/trash`, `/bulk/download` (ZIP) |
| Folders | `GET/POST /api/folders`, `GET/PATCH/DELETE /api/folders/{id}`, `POST /api/folders/{id}/trash`, `/restore` |
| Trash | `POST /api/trash/restore`, `/delete`, `/restore-all`, `/empty` |
| Secure vault | `GET/POST /api/vault` (status / create), `POST /api/vault/password`, `POST /api/vault/reset`, `GET/POST /api/vault/files`, `GET /api/vault/files/{id}/preview` · `/download`, `PATCH/DELETE /api/vault/files/{id}`, `POST /api/vault/files/{id}/move-out`, `POST /api/vault/import/{file_id}` – file routes need the `X-Vault-Password` header |
| Sharing (M2) | `POST/GET /api/files/{id}/shares` (create link or direct share / list), `GET /api/shares/sent`, `GET /api/shares/received`, `POST /api/shares/bulk` (several files at once), `POST /api/folders/{id}/shares` (a whole folder), `GET /api/shares/{id}/access` (access history), `PATCH /api/shares/{id}` (edit permission / expiry / limit), `DELETE /api/shares/{id}` (revoke), `GET /api/shares/{id}/preview` · `/download` (recipient) |
| Analytics (M2) | `GET /api/analytics/me?from&to&tz`, `GET /api/files/storage`, `GET /api/files/recent`, `GET /api/files/favorites`, `PUT/DELETE /api/files/{id}/favorite`, `GET /api/activity/me` |
| Admin reports (M2) | `GET /api/admin/overview` (`user:read`), `GET /api/admin/security/overview`, `/security/logins`, `/security/events`, `GET /api/admin/audit`, `GET /api/admin/audit/export` (CSV) (`audit:read`) |
| Activity monitoring (M3) | `GET /api/activity-monitoring/activities`, `/summary`, `/types`, `/stream` (SSE) – `audit:read` |
| Audit logs (M3) | `GET /api/audit-logs`, `/audit-logs/user/{user_id}`, `/audit-logs/file/{file_id}`, `/audit-logs/filter` (incl. an exact `since` / `until` window), `/audit-logs/verify`, `/audit-logs/export` (CSV) – `audit:read` |
| Notifications (M3) | `GET /api/notifications`, `/unread-count`, `POST /{id}/read`, `/read-all`, `GET/PUT /preferences`, `GET /stream` (SSE); `GET /api/notifications/admin/stats` (`audit:read`) |
| Security monitoring (M3) | `GET /api/security-monitoring/summary`, `/events`, `GET/PATCH /events/{id}` (acknowledge / resolve / reopen), `/rules` – `audit:read` |
| Reports (M3) | `GET /api/reports/uploads`, `/downloads`, `/sharing`, `/users/{id}`, `/security` (`format=csv`) – `audit:read` |
| Storage analytics (M3) | `GET /api/analytics/storage`, `/analytics/users/storage`, `/analytics/files`, `/analytics/downloads`, `/analytics/sharing` – `audit:read` |
| Public links (M2) | `GET /api/s/{token}` · `/preview` · `/download` – no login, rate-limited per IP; password-protected links need the `X-Share-Password` header (wrong or missing → `403`, 5 wrong → `429` for 15 min) |
