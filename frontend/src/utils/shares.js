import { formatDate } from './format';

// Text helpers for shares (Share dialog, "Shared by me", "Shared with me", public page).

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
