import { useCallback, useEffect, useMemo, useState } from 'react';

import { DARK_QUERY, readPreference, savePreference } from './theme';
import { ThemeContext } from './ThemeContext';

/**
 * Holds the workspace's light/dark choice for the whole app. "System" follows the operating
 * system live (e.g. when Windows switches to dark in the evening). The workspace layout applies
 * the result to the page (see DashboardLayout); this provider only decides what it is.
 */
export default function ThemeProvider({ children }) {
  const [preference, setPreferenceState] = useState(readPreference);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia(DARK_QUERY).matches);

  useEffect(() => {
    const media = window.matchMedia(DARK_QUERY);
    const onChange = (event) => setSystemDark(event.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;

  const setPreference = useCallback((next) => {
    savePreference(next);
    setPreferenceState(next);
  }, []);

  // The header's sun/moon button: switch to the opposite of what is shown right now.
  const toggle = useCallback(
    () => setPreference(resolved === 'dark' ? 'light' : 'dark'),
    [resolved, setPreference],
  );

  const value = useMemo(
    () => ({ preference, resolved, setPreference, toggle }),
    [preference, resolved, setPreference, toggle],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
