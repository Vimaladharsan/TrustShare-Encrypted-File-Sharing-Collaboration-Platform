import { api } from './client';

// Admin-only user management (see backend app/api/routes/admin.py).

export async function listUsers({ search = '', limit = 20, offset = 0 } = {}) {
  const params = { limit, offset };
  if (search) params.search = search;
  const { data } = await api.get('/admin/users', { params });
  return data; // { items, total }
}

/** changes: { role?: 'admin' | 'user' | 'guest', is_active?: boolean } */
export async function updateUser(userId, changes) {
  const { data } = await api.patch(`/admin/users/${userId}`, changes);
  return data;
}

export async function unlockUser(userId) {
  const { data } = await api.post(`/admin/users/${userId}/unlock`);
  return data;
}
