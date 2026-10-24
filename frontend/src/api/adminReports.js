import { api } from './client';
import { saveBlob } from './files';

// Admin-only reports (backend app/api/routes/admin_reports.py). The server checks the
// permissions (audit:read / user:read) on every call.

const timeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

function rangeParams({ from, to } = {}) {
  const params = { tz: timeZone() };
  if (from) params.from = from;
  if (to) params.to = to;
  return params;
}

export async function getSecurityOverview(range) {
  const { data } = await api.get('/admin/security/overview', { params: rangeParams(range) });
  return data;
}

export async function getSystemOverview(range) {
  const { data } = await api.get('/admin/overview', { params: rangeParams(range) });
  return data;
}

export async function getLogins({ status, limit = 25, offset = 0 } = {}) {
  const params = { limit, offset };
  if (status) params.status = status;
  const { data } = await api.get('/admin/security/logins', { params });
  return data;
}

export async function getSecurityEvents({ severity, limit = 25, offset = 0 } = {}) {
  const params = { limit, offset };
  if (severity) params.severity = severity;
  const { data } = await api.get('/admin/security/events', { params });
  return data;
}

export async function getAuditLog({ q, group, status, limit = 25, offset = 0 } = {}) {
  const params = { limit, offset };
  if (q) params.q = q;
  if (group) params.group = group;
  if (status) params.status = status;
  const { data } = await api.get('/admin/audit', { params });
  return data;
}

export async function getHealth() {
  const { data } = await api.get('/health');
  return data;
}

/** Downloads the audit log (same filters as the viewer, max 10,000 rows) as a CSV file. */
export async function exportAuditLog({ q, group, status } = {}) {
  const params = {};
  if (q) params.q = q;
  if (group) params.group = group;
  if (status) params.status = status;
  const response = await api.get('/admin/audit/export', { params, responseType: 'blob' });
  const match = /filename="([^"]+)"/.exec(response.headers['content-disposition'] || '');
  saveBlob(response.data, match ? match[1] : 'trustshare-audit.csv');
}
