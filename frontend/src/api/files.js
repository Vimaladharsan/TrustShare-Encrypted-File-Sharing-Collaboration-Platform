import { api } from './client';

// Wrappers around the file and folder endpoints (backend app/api/routes/files.py, folders.py).

// ---------- files ----------

/** folderId: undefined/null = top level, 'all' = every folder (search). */
export async function listFiles({ folderId, trashed, q, category, sort, order } = {}) {
  const params = { sort, order, limit: 200 };
  if (folderId) params.folder_id = folderId;
  if (trashed) params.trashed = true;
  if (q) params.q = q;
  if (category) params.category = category;
  const { data } = await api.get('/files', { params });
  return data.items;
}

export async function getUsage() {
  const { data } = await api.get('/files/usage');
  return data;
}

export async function updateFile(fileId, changes) {
  const { data } = await api.patch(`/files/${fileId}`, changes);
  return data;
}

export const trashFile = (fileId) => api.post(`/files/${fileId}/trash`);
export const restoreFile = (fileId) => api.post(`/files/${fileId}/restore`);
export const deleteFile = (fileId) => api.delete(`/files/${fileId}`);

/** Downloads through the API (so the login token is sent), then saves it in the browser. */
export async function downloadFile(file) {
  const response = await api.get(`/files/${file.id}/download`, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = file.name;
  link.click();
  URL.revokeObjectURL(url);
}

// ---------- folders ----------

export async function listFolders({ parentId, trashed } = {}) {
  const params = {};
  if (parentId) params.parent_id = parentId;
  if (trashed) params.trashed = true;
  const { data } = await api.get('/folders', { params });
  return data.items;
}

/** Folder details including breadcrumbs (top-level folder → this folder). */
export async function getFolder(folderId) {
  const { data } = await api.get(`/folders/${folderId}`);
  return data;
}

export async function createFolder(name, parentId) {
  const { data } = await api.post('/folders', { name, parent_id: parentId || null });
  return data;
}

export async function updateFolder(folderId, changes) {
  const { data } = await api.patch(`/folders/${folderId}`, changes);
  return data;
}

export const trashFolder = (folderId) => api.post(`/folders/${folderId}/trash`);
export const restoreFolder = (folderId) => api.post(`/folders/${folderId}/restore`);
