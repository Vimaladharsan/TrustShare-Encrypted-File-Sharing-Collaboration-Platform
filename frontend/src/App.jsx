import { lazy, Suspense } from 'react';
import { Link, Route, Routes } from 'react-router';

import DashboardLayout from './components/layout/DashboardLayout';
import ProtectedRoute from './components/ProtectedRoute';
import { Loading } from './components/StateMessage';
import ActivityPage from './pages/ActivityPage';
import AdminUsersPage from './pages/AdminUsersPage';
import DashboardPage from './pages/DashboardPage';
import FavoritesPage from './pages/FavoritesPage';
import FilesPage from './pages/FilesPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import GoogleCallbackPage from './pages/GoogleCallbackPage';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import PublicSharePage from './pages/PublicSharePage';
import RecentPage from './pages/RecentPage';
import RegisterPage from './pages/RegisterPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import SecurityPage from './pages/SecurityPage';
import SettingsPage from './pages/SettingsPage';
import SharedByMePage from './pages/SharedByMePage';
import SharedWithMePage from './pages/SharedWithMePage';
import StatusPage from './pages/StatusPage';
import StoragePage from './pages/StoragePage';
import TrashPage from './pages/TrashPage';
import VerifyEmailPage from './pages/VerifyEmailPage';

// The charts library is large, so the analytics page is downloaded only when it is opened.
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));

// URL → page mapping. "/" is the public landing page. Everything inside <ProtectedRoute> needs a
// logged-in user and is shown inside the dashboard frame (sidebar + top bar).
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/auth/google" element={<GoogleCallbackPage />} />
      <Route path="/status" element={<StatusPage />} />
      {/* Share links work without an account. */}
      <Route path="/s/:token" element={<PublicSharePage />} />
      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/files" element={<FilesPage />} />
        <Route path="/folders/:folderId" element={<FilesPage />} />
        <Route path="/search" element={<FilesPage mode="search" />} />
        <Route path="/shared-with-me" element={<SharedWithMePage />} />
        <Route path="/shared-by-me" element={<SharedByMePage />} />
        <Route path="/recent" element={<RecentPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/trash" element={<TrashPage />} />
        <Route path="/storage" element={<StoragePage />} />
        <Route
          path="/analytics"
          element={
            <Suspense fallback={<Loading />}>
              <AnalyticsPage />
            </Suspense>
          }
        />
        <Route path="/activity" element={<ActivityPage />} />
        <Route path="/security" element={<SecurityPage />} />
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
