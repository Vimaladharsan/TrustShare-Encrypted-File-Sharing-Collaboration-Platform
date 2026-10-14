import { Link, Route, Routes } from 'react-router';

import DashboardLayout from './components/layout/DashboardLayout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminUsersPage from './pages/AdminUsersPage';
import FilesPage from './pages/FilesPage';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import SettingsPage from './pages/SettingsPage';
import StatusPage from './pages/StatusPage';
import TrashPage from './pages/TrashPage';

// URL → page mapping. "/" is the public landing page. Everything inside <ProtectedRoute> needs a
// logged-in user and is shown inside the dashboard frame (sidebar + top bar).
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/status" element={<StatusPage />} />
      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/files" element={<FilesPage />} />
        <Route path="/folders/:folderId" element={<FilesPage />} />
        <Route path="/search" element={<FilesPage mode="search" />} />
        <Route path="/trash" element={<TrashPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 text-center">
      <p className="text-sm font-semibold text-blue-600">404</p>
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <Link to="/" className="text-sm text-blue-600 hover:underline">
        Go home
      </Link>
    </main>
  );
}
