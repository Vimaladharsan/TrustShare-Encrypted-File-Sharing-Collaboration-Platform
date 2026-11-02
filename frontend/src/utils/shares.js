import { formatDate } from './format';

// Helpers for shares (Share dialog, Edit share, "Shared by me", "Shared with me", public page).

export const HOUR = 60 * 60 * 1000;
export const LINK_MAX_DAYS = 30; // the server's SHARE_LINK_MAX_DAYS

/** Value for <input type="datetime-local">: local time, minutes precision. */
export function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

/** Problem with a custom expiry, or '' if it is fine. shareType: 'link' | 'user'. */
export function customExpiryError(value, shareType) {
  if (!value) return 'Pick a date and time.';
  const when = new Date(value).getTime();
  if (Number.isNaN(when) || when <= Date.now()) return 'Pick a time in the future.';
  if (shareType === 'link' && when > Date.now() + LINK_MAX_DAYS * 24 * HOUR) {
    return `Links can last at most ${LINK_MAX_DAYS} days.`;
  }
  return '';
}

export const permissionLabel = (permission) =>
  permission === 'download' ? 'View & download' : 'View only';

/** "Expires 30 Oct 2026, 14:05" / "No expiry" */
export function expiryLabel(expiresAt) {
  if (!expiresAt) return 'No expiry';
  const date = new Date(expiresAt);
  const time = date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  return `${formatDate(expiresAt)}, ${time}`;
}

/** "3 / 5" with a limit, "3" without. */
export const downloadsLabel = (share) =>
  share.max_downloads ? `${share.download_count} / ${share.max_downloads}` : share.download_count;
