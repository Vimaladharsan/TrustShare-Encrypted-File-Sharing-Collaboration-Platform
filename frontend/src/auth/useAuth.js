import { useContext } from 'react';

import { AuthContext } from './AuthContext';

/** Access the logged-in user and the login/logout functions from any component. */
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>');
  return value;
}
