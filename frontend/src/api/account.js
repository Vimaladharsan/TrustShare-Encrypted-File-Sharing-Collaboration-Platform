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
