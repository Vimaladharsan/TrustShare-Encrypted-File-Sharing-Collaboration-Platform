import axios from 'axios';

/**
 * One shared Axios instance for every backend call.
 * - baseURL '/api': same origin as the app; Vite forwards it to FastAPI.
 * - withCredentials: sends the HttpOnly refresh-token cookie (JavaScript can't read it).
 */
export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 30000,
});

// ---------- access token: kept in memory only (never localStorage) ----------

let accessToken = null;
let onSessionExpired = () => {};

export function setAccessToken(token) {
  accessToken = token;
}

/** Called by AuthProvider: what to do when the session can't be renewed (go to login). */
export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

// ---------- refresh: "single-flight" ----------
// Several requests can fail with 401 at the same time (and React StrictMode runs startup code
// twice). They must all share ONE refresh call: using the same refresh token twice looks like
// token theft to the server, which would then log the user out everywhere.

let refreshPromise = null;

export function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = axios
      .post('/api/auth/refresh', null, { withCredentials: true })
      .then(({ data }) => {
        setAccessToken(data.access_token);
        return data;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// Endpoints where a 401 means "wrong credentials", not "token expired".
const NO_RETRY = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/mfa/verify'];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // File downloads ask for a Blob, so an error body arrives as a Blob too – turn the JSON
    // error back into an object so the real message ("This link was revoked…") can be shown.
    const body = error.response?.data;
    if (typeof Blob !== 'undefined' && body instanceof Blob && body.type.includes('json')) {
      try {
        error.response.data = JSON.parse(await body.text());
      } catch {
        // not JSON after all – keep the generic message
      }
    }
    const original = error.config;
    const isAuthCall = NO_RETRY.some((path) => original?.url?.startsWith(path));
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      try {
        await refreshSession();
        return api(original); // retry once with the new access token
      } catch {
        setAccessToken(null);
        onSessionExpired();
      }
    }
    return Promise.reject(error);
  },
);

/** Turns any error into a readable message, using the backend's standard error format. */
export function getErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const apiError = error?.response?.data?.error;
  if (apiError?.code === 'VALIDATION_ERROR' && apiError.details?.length) {
    return apiError.details[0].message.replace(/^Value error, /, '');
  }
  if (apiError?.message) return apiError.message;
  if (error?.code === 'ECONNABORTED') return 'The server took too long to respond.';
  if (error?.request && !error?.response) return 'Cannot reach the server. Is the backend running?';
  return fallback;
}

/** The backend's machine-readable error code (e.g. "INVALID_CREDENTIALS"), if any. */
export function getErrorCode(error) {
  return error?.response?.data?.error?.code;
}
