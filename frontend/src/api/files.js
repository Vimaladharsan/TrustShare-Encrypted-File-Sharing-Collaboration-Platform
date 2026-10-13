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

/**
 * Upload one file as multipart form data.
 * onProgress(percent) is called as bytes are sent; signal lets the user cancel.
 */
export async function uploadFile(file, { folderId, allowDuplicate, onProgress, signal } = {}) {
  const form = new FormData();
  form.append('file', file);
  const params = {};
  if (folderId) params.folder_id = folderId;
  if (allowDuplicate) params.allow_duplicate = true;
  const { data } = await api.post('/files', form, {
    params,
    signal,
    timeout: 0, // large files on slow connections can take longer than the default 30 s
    onUploadProgress: (event) => {
      if (event.total) onProgress?.(Math.round((event.loaded / event.total) * 100));
    },
  });
  return data;
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
export const deleteFolder = (folderId) => api.delete(`/folders/${folderId}`);

// ---------- trash (bulk) ----------
// Each returns { succeeded, failed: [{ id, type, code, message }] }.

export async function restoreSelected(fileIds, folderIds) {
  const { data } = await api.post('/trash/restore', { file_ids: fileIds, folder_ids: folderIds });
  return data;
}

export async function deleteSelected(fileIds, folderIds) {
  const { data } = await api.post('/trash/delete', { file_ids: fileIds, folder_ids: folderIds });
  return data;
}

export async function restoreAll() {
  const { data } = await api.post('/trash/restore-all');
  return data;
}

export async function emptyTrash() {
  const { data } = await api.post('/trash/empty');
  return data;
}
