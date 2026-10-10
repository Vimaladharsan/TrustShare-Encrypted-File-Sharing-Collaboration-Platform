import { Navigate, Route, Routes } from 'react-router';

import StatusPage from './pages/StatusPage';

// URL → page mapping. Login, dashboard etc. are added in later phases.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/status" replace />} />
      <Route path="/status" element={<StatusPage />} />
      <Route path="*" element={<p className="p-8">Page not found</p>} />
    </Routes>
  );
}
