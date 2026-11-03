import { useLocation } from 'react-router';
import { Toaster } from 'sonner';

import { isPublicPath } from '../theme/theme';
import { useTheme } from '../theme/useTheme';

/** Toasts match the page they appear on: console dark, public pages light, workspace = its mode. */
export default function ThemedToaster() {
  const { pathname } = useLocation();
  const { resolved } = useTheme();
  const theme = pathname.startsWith('/admin')
    ? 'dark'
    : isPublicPath(pathname)
      ? 'light'
      : resolved;
  return <Toaster position="bottom-right" richColors closeButton theme={theme} />;
}
