import { Loader2 } from 'lucide-react';
import { Navigate } from 'react-router';

import { useAuth } from '../auth/useAuth';

/**
 * Where the backend sends the browser after a successful Google login (/auth/google).
 * The backend has already set the refresh-token cookie; on page load the AuthProvider swaps it
 * for an access token (/auth/refresh) like after any reload – so here we only wait for that.
 */
export default function GoogleCallbackPage() {
  const { status } = useAuth();

  if (status === 'authenticated') return <Navigate to="/files" replace />;
  if (status === 'anonymous') {
    const message = 'Google sign-in could not be completed. Please try again.';
    return <Navigate to={`/login?oauth_error=${encodeURIComponent(message)}`} replace />;
  }
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 text-slate-500">
      <Loader2 className="size-8 animate-spin text-blue-600" aria-label="Signing in" />
      Signing you in with Google…
    </main>
  );
}
