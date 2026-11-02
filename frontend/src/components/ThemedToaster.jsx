import { useLocation } from 'react-router';
import { Toaster } from 'sonner';

/** Toasts match where they appear: dark in the admin console, light in the workspace. */
export default function ThemedToaster() {
  const { pathname } = useLocation();
  const theme = pathname.startsWith('/admin') ? 'dark' : 'light';
  return <Toaster position="bottom-right" richColors closeButton theme={theme} />;
}
