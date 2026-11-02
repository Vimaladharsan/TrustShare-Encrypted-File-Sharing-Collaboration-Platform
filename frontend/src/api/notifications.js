import { api, getAccessToken, refreshSession } from './client';

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

/**
 * Live notifications (Server-Sent Events). Read with fetch() so the access token travels in the
 * Authorization header – never in the URL. Reconnects by itself:
 *   reauth    → the token expired or this device was signed out: refresh, then reconnect
 *   reconnect → the server's maximum stream age was reached
 *   network error → retry with a growing delay (2 s … 30 s)
 * `onEvent(name, data)` receives "ready" and "notification". Returns a stop() function.
 */
export function openNotificationStream(onEvent) {
  let stopped = false;
  let controller = null;
  let delay = 2000;

  async function connect() {
    while (!stopped) {
      controller = new AbortController();
      let next = 'retry';
      try {
        const response = await fetch('/api/notifications/stream', {
          headers: { Authorization: `Bearer ${getAccessToken()}`, Accept: 'text/event-stream' },
          credentials: 'include',
          signal: controller.signal,
        });
        if (response.status === 401) {
          next = 'reauth';
        } else if (response.ok && response.body) {
          delay = 2000;
          next = await readEvents(response.body, onEvent);
        }
      } catch {
        if (stopped) return;
      }
      if (stopped) return;
      if (next === 'reauth') {
        try {
          await refreshSession();
          continue;
        } catch {
          return; // not signed in any more – the app sends the user to the login page
        }
      }
      if (next === 'reconnect') continue;
      await new Promise((resolve) => setTimeout(resolve, delay));
      delay = Math.min(delay * 2, 30000);
    }
  }

  connect();
  return () => {
    stopped = true;
    controller?.abort();
  };
}

/** Parse "event: x\ndata: {...}\n\n" blocks. Resolves with why the stream ended. */
async function readEvents(body, onEvent) {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return 'retry';
    buffer += value;
    let end;
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let name = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) name = line.slice(7);
        else if (line.startsWith('data: ')) data += line.slice(6);
      }
      if (name === 'reauth' || name === 'reconnect') return name;
      if (data) {
        try {
          onEvent(name, JSON.parse(data));
        } catch {
          // ignore a malformed event
        }
      }
    }
  }
}
