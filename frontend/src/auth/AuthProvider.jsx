import { useCallback, useEffect, useMemo, useState } from 'react';

import * as authApi from '../api/auth';
import { refreshSession, setSessionExpiredHandler } from '../api/client';
import { AuthContext } from './AuthContext';

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading');

  const clearSession = useCallback(() => {
    setUser(null);
    setStatus('anonymous');
  }, []);

  // On page load: the access token (memory) is gone, but the HttpOnly refresh cookie may still
  // be valid – try to resume the session silently.
  useEffect(() => {
    setSessionExpiredHandler(clearSession);
    refreshSession()
      .then((data) => {
        setUser(data.user);
        setStatus('authenticated');
      })
      .catch(clearSession);
  }, [clearSession]);

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password);
    if (data.mfa_required) return data; // the page shows the code step next
    setUser(data.user);
    setStatus('authenticated');
    return data;
  }, []);

  const completeMfa = useCallback(async (challengeId, code) => {
    const data = await authApi.verifyMfa(challengeId, code);
    setUser(data.user);
    setStatus('authenticated');
    return data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo(
    () => ({
      user,
      status,
      login,
      completeMfa,
      logout,
      register: authApi.register,
      can: (permission) => Boolean(user?.permissions.includes(permission)),
    }),
    [user, status, login, completeMfa, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
