import { createContext } from 'react';

/**
 * The signed-in user's notifications, shared with the whole app (bell, page, settings).
 * { unread, recent, version, live, markOne, markAll, reload }
 * `version` goes up whenever a new notification arrives, so pages can reload their lists.
 */
export const NotificationsContext = createContext(null);
