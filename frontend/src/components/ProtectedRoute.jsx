import { Loader2 } from 'lucide-react';
import { Navigate, useLocation } from 'react-router';

import { useAuth } from '../auth/useAuth';

/** Shows the page only to logged-in users; everyone else is sent to /login (and back after). */
export default function ProtectedRoute({ children }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        <Loader2 className="size-6 animate-spin" aria-label="Loading" />
      </div>
    );
  }
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
