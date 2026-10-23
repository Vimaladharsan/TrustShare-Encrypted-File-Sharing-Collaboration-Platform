import { api } from './client';
import { saveBlob } from './files';

// Sharing (backend app/api/routes/shares.py).

// ---------- owner ----------

/**
 * body: { share_type: 'link' | 'user', permission: 'view' | 'download',
 *         expires_at?: ISO string, max_downloads?: number, recipient_email?: string }
 * For links the response contains `url` – shown once, the server keeps only its hash.
 */
export async function createShare(fileId, body) {
  const { data } = await api.post(`/files/${fileId}/shares`, body);
  return data;
}

export async function listFileShares(fileId) {
  const { data } = await api.get(`/files/${fileId}/shares`);
  return data.items;
}

export async function listSentShares() {
  const { data } = await api.get('/shares/sent');
  return data.items;
}

export const revokeShare = (shareId) => api.delete(`/shares/${shareId}`);

// ---------- recipient ("Shared with me") ----------

export async function listReceivedShares() {
  const { data } = await api.get('/shares/received');
  return data.items;
}

export async function previewReceived(shareId, signal) {
  const response = await api.get(`/shares/${shareId}/preview`, { responseType: 'blob', signal });
  return response.data;
}

export async function downloadReceived(share) {
  const response = await api.get(`/shares/${share.id}/download`, { responseType: 'blob' });
  saveBlob(response.data, share.file_name);
}

// ---------- public link (no login needed) ----------

export async function getPublicShare(token) {
  const { data } = await api.get(`/s/${token}`);
  return data;
}

export async function previewPublic(token, signal) {
  const response = await api.get(`/s/${token}/preview`, { responseType: 'blob', signal });
  return response.data;
}

export async function downloadPublic(token, name) {
  const response = await api.get(`/s/${token}/download`, { responseType: 'blob' });
  saveBlob(response.data, name);
}
