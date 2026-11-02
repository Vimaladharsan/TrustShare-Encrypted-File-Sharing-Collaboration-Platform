import { api } from './client';
import { openEventStream } from './stream';

// Notifications (backend app/notifications/routes.py).

export async function listNotifications({ unread = false, type, limit = 20, offset = 0 } = {}) {
  const params = { limit, offset };
  if (unread) params.unread = true;
  if (type) params.type = type;
  const { data } = await api.get('/notifications', { params });
  return data;
}

export const markRead = (id) => api.post(`/notifications/${id}/read`);
export const markAllRead = () => api.post('/notifications/read-all');

export async function getPreferences() {
  const { data } = await api.get('/notifications/preferences');
  return data.items;
}

export async function updatePreferences(email) {
  const { data } = await api.put('/notifications/preferences', { email });
  return data.items;
}

/** Live notifications – see api/stream.js. `onEvent(name, data)`: "ready", "notification". */
export function openNotificationStream(onEvent) {
  return openEventStream('/api/notifications/stream', onEvent);
}
