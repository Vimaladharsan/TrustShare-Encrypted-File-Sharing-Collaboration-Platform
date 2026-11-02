// Desktop pop-ups (the browser's Notification API) for new notifications that arrive while
// TrustShare is in a background tab. They are a per-device choice: the browser asks for permission
// once per site and device, and the on/off switch is kept in this browser (localStorage) – not on
// the account. Pop-ups only appear while TrustShare is open somewhere in the background.

const KEY = 'trustshare.desktopPopups';

/** The browser can show desktop notifications here (needs HTTPS or localhost). */
export const desktopSupported = () =>
  typeof window !== 'undefined' && 'Notification' in window && window.isSecureContext;

/** 'granted' | 'denied' | 'default' (not asked yet) | 'unsupported' */
export const desktopPermission = () =>
  desktopSupported() ? window.Notification.permission : 'unsupported';

function switchedOn() {
  try {
    return localStorage.getItem(KEY) === 'on';
  } catch {
    return false; // storage blocked (private mode): treat as off
  }
}

/** On = the user turned it on in Settings AND the browser still allows it. */
export const desktopEnabled = () => switchedOn() && desktopPermission() === 'granted';

export function disableDesktop() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing stored, nothing to remove
  }
}

/** Asks the browser for permission (must run from a click). Returns the resulting permission. */
export async function enableDesktop() {
  const permission = await window.Notification.requestPermission();
  if (permission === 'granted') {
    try {
      localStorage.setItem(KEY, 'on');
    } catch {
      return 'storage-blocked';
    }
  }
  return permission;
}

/**
 * Shows `notification` as a desktop pop-up if the tab is in the background and pop-ups are on.
 * Clicking it brings TrustShare to the front and calls onOpen(notification).
 */
export function showDesktop(notification, onOpen) {
  if (!document.hidden || !desktopEnabled()) return;
  const popup = new window.Notification(notification.title, {
    body: notification.message,
    tag: notification.id, // the same notification never pops up twice
  });
  popup.onclick = () => {
    window.focus();
    onOpen?.(notification);
    popup.close();
  };
}
