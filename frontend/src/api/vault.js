import { api } from './client';
import { saveBlob } from './files';

// Secure vault (backend app/api/routes/vault.py). The vault password goes with EVERY file
// request in a header (URL-encoded so any character works). It is never stored in the browser.

const withPassword = (password, extra = {}) => ({
  ...extra,
  headers: { ...extra.headers, 'X-Vault-Password': encodeURIComponent(password) },
});

export async function getVaultStatus() {
  const { data } = await api.get('/vault');
  return data;
}

export const createVault = (password) => api.post('/vault', { password });

export const changeVaultPassword = (currentPassword, newPassword) =>
  api.post('/vault/password', { current_password: currentPassword, new_password: newPassword });

/** body: { account_password?, confirm } – deletes the vault and everything in it. */
export async function resetVault(body) {
  const { data } = await api.post('/vault/reset', body);
  return data;
}

export async function listVaultFiles(password) {
  const { data } = await api.get('/vault/files', withPassword(password));
  return data.items;
}

export async function uploadToVault(file, password) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/vault/files', form, withPassword(password));
  return data;
}

export async function previewVaultFile(fileId, password, signal) {
  const response = await api.get(
    `/vault/files/${fileId}/preview`,
    withPassword(password, { responseType: 'blob', signal }),
  );
  return response.data;
}

export async function downloadVaultFile(file, password) {
  const response = await api.get(
    `/vault/files/${file.id}/download`,
    withPassword(password, { responseType: 'blob' }),
  );
  saveBlob(response.data, file.name);
}

export async function renameVaultFile(fileId, name, password) {
  const { data } = await api.patch(`/vault/files/${fileId}`, { name }, withPassword(password));
  return data;
}

export const deleteVaultFile = (fileId, password) =>
  api.delete(`/vault/files/${fileId}`, withPassword(password));

export const moveOutOfVault = (fileId, password) =>
  api.post(`/vault/files/${fileId}/move-out`, null, withPassword(password));

export const moveIntoVault = (fileId, password) =>
  api.post(`/vault/import/${fileId}`, null, withPassword(password));
