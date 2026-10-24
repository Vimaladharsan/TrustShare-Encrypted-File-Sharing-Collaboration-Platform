import { api, setAccessToken } from './client';

// The logged-in user's own account settings (see backend app/api/routes/users.py).

export async function getMfaStatus() {
  const { data } = await api.get('/users/me/mfa');
  return data; // { enabled, backup_codes_remaining }
}

/** Step 1: a new secret + QR code. Nothing changes until the code is confirmed. */
export async function startMfaSetup() {
  const { data } = await api.post('/users/me/mfa/setup');
  return data; // { secret, otpauth_uri, qr_code, expires_in }
}

/** Step 2: confirm with a code from the app. Returns the one-time backup codes. */
export async function enableMfa(code) {
  const { data } = await api.post('/users/me/mfa/enable', { code });
  return data.backup_codes;
}

export async function disableMfa(password, code) {
  await api.post('/users/me/mfa/disable', { password, code });
}

/** Changes the password. Other devices are logged out; this one gets a new session. */
export async function changePassword(currentPassword, newPassword) {
  const { data } = await api.post('/users/me/password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
  setAccessToken(data.access_token); // the old token stopped working with the change
  return data;
}

/** Change my display name; returns the updated profile. */
export async function updateProfile(fullName) {
  const { data } = await api.patch('/users/me', { full_name: fullName });
  return data;
}

/** My signed-in devices: [{ id, browser, os, kind, ip_address, location, signed_in_at, last_active_at, current }] */
export async function getDevices() {
  const { data } = await api.get('/users/me/sessions');
  return data.items;
}

export const signOutDevice = (sessionId) => api.delete(`/users/me/sessions/${sessionId}`);

/** New backup codes (needs a current authenticator code); the old codes stop working. */
export async function regenerateBackupCodes(code) {
  const { data } = await api.post('/users/me/mfa/backup-codes', { code });
  return data.backup_codes;
}

/** Permanently delete my account: { password?, code?, confirm } */
export async function deleteAccount(body) {
  await api.delete('/users/me', { data: body });
}
