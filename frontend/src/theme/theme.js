// Light / dark mode for the user workspace. The choice ("light", "dark" or "system" = follow the
// operating system) is a per-device preference kept in this browser (localStorage). Public pages
// (landing, sign-in, share links) always stay light; the admin console is always dark.
// public/theme-init.js applies the saved choice before the app starts – keep both in sync.

export const THEME_KEY = 'trustshare.theme';
export const THEMES = ['light', 'dark', 'system'];

export function readPreference() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return THEMES.includes(saved) ? saved : 'light';
  } catch {
    return 'light'; // storage blocked (private mode)
  }
}

export function savePreference(preference) {
  try {
    localStorage.setItem(THEME_KEY, preference);
  } catch {
    // not remembered in this browser – it still applies until the page is reloaded
  }
}

export const DARK_QUERY = '(prefers-color-scheme: dark)';

/** Pages outside the workspace (no sidebar) – always shown in light mode. */
export function isPublicPath(pathname) {
  return (
    pathname === '/' ||
    /^\/(login|register|forgot-password|reset-password|verify-email|auth\/google|status|s\/)/.test(
      pathname,
    )
  );
}
