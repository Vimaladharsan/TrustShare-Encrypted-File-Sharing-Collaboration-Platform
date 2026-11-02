import { api } from './client';
import { saveBlob } from './files';
import { openEventStream } from './stream';

// Milestone 3 admin APIs: activity monitoring, audit logs, security monitoring, reports,
// storage analytics, notification management. The server checks `audit:read` on every call.

const timeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

/** Drop empty values and add the browser's time zone. */
function clean(params = {}) {
  const out = { tz: timeZone() };
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined && key !== 'preset') out[key] = value;
  });
  return out;
}

async function get(url, params) {
  const { data } = await api.get(url, { params: clean(params) });
  return data;
}

async function download(url, params, name) {
  const response = await api.get(url, { params: clean(params), responseType: 'blob' });
  saveBlob(response.data, name);
}

// ---------- activity monitoring ----------
export const getActivities = (params) => get('/activity-monitoring/activities', params);
export const getActivitySummary = (params) => get('/activity-monitoring/summary', params);
export const openActivityStream = (onEvent) =>
  openEventStream('/api/activity-monitoring/stream', onEvent);

// ---------- audit logs ----------
export const filterAuditLogs = (params) => get('/audit-logs/filter', params);
export const verifyAuditLogs = () => get('/audit-logs/verify');
export const exportAuditLogs = (params) =>
  download('/audit-logs/export', params, 'trustshare-audit-logs.csv');

// ---------- security monitoring ----------
export const getMonitoringSummary = (params) => get('/security-monitoring/summary', params);
export const getAlerts = (params) => get('/security-monitoring/events', params);
export const getDetectionRules = () => get('/security-monitoring/rules');
export async function updateAlert(id, action, note) {
  const { data } = await api.patch(`/security-monitoring/events/${id}`, { action, note });
  return data;
}

// ---------- reports ----------
/** name: uploads | downloads | sharing | security | users/<id> */
export const getReport = (name, params) => get(`/reports/${name}`, params);
export const exportReport = (name, params) =>
  download(
    `/reports/${name}`,
    { ...params, format: 'csv' },
    `trustshare-${name.replace('/', '-')}-report.csv`,
  );

// ---------- storage analytics ----------
export const getStorageAnalytics = (params) => get('/analytics/storage', params);
export const getUserStorage = (params) => get('/analytics/users/storage', params);
export const getFileStatistics = (params) => get('/analytics/files', params);
export const getDownloadStatistics = (params) => get('/analytics/downloads', params);
export const getSharingStatistics = (params) => get('/analytics/sharing', params);

// ---------- notification management ----------
export const getNotificationStats = () => get('/notifications/admin/stats');
