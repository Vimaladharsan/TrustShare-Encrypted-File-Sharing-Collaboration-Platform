import axios from 'axios';

// One shared Axios instance for every backend call.
// baseURL '/api' = same origin as the app; Vite forwards it to FastAPI.
// withCredentials = send cookies (needed later for the refresh token).
export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 30000,
});
