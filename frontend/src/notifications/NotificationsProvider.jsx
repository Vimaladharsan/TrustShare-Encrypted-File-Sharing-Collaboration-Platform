import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import {
  listNotifications,
  markAllRead,
  markRead,
  openNotificationStream,
} from '../api/notifications';
import { useAuth } from '../auth/useAuth';
import { NotificationsContext } from './NotificationsContext';

const RECENT = 8;

/**
 * Opens ONE live notification stream while someone is signed in and keeps the unread count and
 * the latest notifications up to date for the whole app. New ones also pop up as a toast.
 */
export default function NotificationsProvider({ children }) {
  const { status } = useAuth();
  const [unread, setUnread] = useState(0);
  const [recent, setRecent] = useState([]);
  const [version, setVersion] = useState(0);
  const [live, setLive] = useState(false);

  const reload = useCallback(async () => {
    try {
      const page = await listNotifications({ limit: RECENT });
      setRecent(page.items);
      setUnread(page.unread);
    } catch {
      // the bell simply shows what it had – the next event or reload fixes it
    }
  }, []);

  useEffect(() => {
    if (status !== 'authenticated') {
      setUnread(0);
      setRecent([]);
      setLive(false);
      return undefined;
    }
    const stop = openNotificationStream((event, data) => {
      if (event === 'ready') {
        setLive(true);
        reload(); // catch up on anything that arrived while disconnected
      } else if (event === 'notification') {
        setRecent((items) => [data, ...items.filter((n) => n.id !== data.id)].slice(0, RECENT));
        setUnread((n) => n + 1);
        setVersion((v) => v + 1);
        const show =
          data.severity === 'critical'
            ? toast.error
            : data.severity === 'warning'
              ? toast.warning
              : toast.info;
        show(data.title, { description: data.message });
      }
    });
    return () => {
      stop();
      setLive(false);
    };
  }, [status, reload]);

  const markOne = useCallback(async (id) => {
    await markRead(id);
    setRecent((items) => items.map((n) => (n.id === id ? { ...n, read: true } : n)));
    setUnread((n) => Math.max(0, n - 1));
    setVersion((v) => v + 1);
  }, []);

  const markAll = useCallback(async () => {
    await markAllRead();
    setRecent((items) => items.map((n) => ({ ...n, read: true })));
    setUnread(0);
    setVersion((v) => v + 1);
  }, []);

  const value = useMemo(
    () => ({ unread, recent, version, live, markOne, markAll, reload }),
    [unread, recent, version, live, markOne, markAll, reload],
  );
  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}
