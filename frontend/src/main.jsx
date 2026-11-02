import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';

import App from './App';
import AuthProvider from './auth/AuthProvider';
import ThemedToaster from './components/ThemedToaster';
import NotificationsProvider from './notifications/NotificationsProvider';
import './index.css';

// Entry point: mount the React app into <div id="root"> in index.html.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <NotificationsProvider>
          <App />
        </NotificationsProvider>
        <ThemedToaster />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
