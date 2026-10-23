import { api } from './client';

// Reports about my own files (backend app/api/routes/analytics.py and files.py).

const timeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

/** range: { from: 'YYYY-MM-DD', to: 'YYYY-MM-DD' }; days are counted in the browser's time zone. */
export async function getAnalytics({ from, to } = {}) {
  const params = { tz: timeZone() };
  if (from) params.from = from;
  if (to) params.to = to;
  const { data } = await api.get('/analytics/me', { params });
  return data;
}

export async function getStorageReport() {
  const { data } = await api.get('/files/storage');
  return data;
}

export async function getRecentFiles() {
  const { data } = await api.get('/files/recent');
  return data.items; // [{ file, last_action, last_activity_at }]
}

export async function getFavorites() {
  const { data } = await api.get('/files/favorites');
  return data.items;
}

export const starFile = (fileId) => api.put(`/files/${fileId}/favorite`);
export const unstarFile = (fileId) => api.delete(`/files/${fileId}/favorite`);

/** group: undefined | 'auth' | 'files' | 'sharing' */
export async function getMyActivity({ group, limit = 25, offset = 0 } = {}) {
  const params = { limit, offset };
  if (group) params.group = group;
  const { data } = await api.get('/activity/me', { params });
  return data; // { items, total }
}
