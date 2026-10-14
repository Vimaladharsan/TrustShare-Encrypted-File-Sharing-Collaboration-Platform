import { api, setAccessToken } from './client';

// Thin wrappers around the auth endpoints (see backend app/api/routes/auth.py).

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password });
  // Either tokens, or { mfa_required: true, challenge_id } when two-step verification is on.
  if (data.access_token) setAccessToken(data.access_token);
  return data;
}

export async function verifyMfa(challengeId, code) {
  const { data } = await api.post('/auth/mfa/verify', { challenge_id: challengeId, code });
  setAccessToken(data.access_token);
  return data;
}

export async function register(fullName, email, password) {
  const { data } = await api.post('/auth/register', { full_name: fullName, email, password });
  return data;
}

export async function logout() {
  try {
    await api.post('/auth/logout');
  } finally {
    setAccessToken(null);
  }
}

export async function fetchMe() {
  const { data } = await api.get('/users/me');
  return data;
}

// ---------- forgot / reset password ----------

export async function forgotPassword(email) {
  const { data } = await api.post('/auth/forgot-password', { email });
  return data.message;
}

export async function resetPassword(token, newPassword) {
  const { data } = await api.post('/auth/reset-password', { token, new_password: newPassword });
  return data.message;
}

// ---------- email verification ----------

export async function verifyEmail(token) {
  const { data } = await api.post('/auth/verify-email', { token });
  return data.message;
}

export async function resendVerification() {
  const { data } = await api.post('/auth/verify-email/resend');
  return data.message;
}

// ---------- Google login ----------

/** Which extra login methods the server has set up, e.g. { google: true }. */
export async function getProviders() {
  const { data } = await api.get('/auth/providers');
  return data;
}
