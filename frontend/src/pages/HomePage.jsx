import { LogOut } from 'lucide-react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import { useAuth } from '../auth/useAuth';
import Button from '../components/Button';
import Logo from '../components/Logo';

/** Temporary home page after login. Replaced by the file dashboard in Phase 5B. */
export default function HomePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    toast.success('You have been logged out.');
    navigate('/login');
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <div className="flex items-center justify-between">
        <Logo />
        <Button variant="secondary" onClick={handleLogout}>
          <LogOut className="size-4" aria-hidden="true" />
          Log out
        </Button>
      </div>

      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Welcome, {user.full_name}</h1>
        <p className="mt-1 text-sm text-slate-500">{user.email}</p>
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-slate-500">Role</dt>
            <dd className="font-medium capitalize">{user.role}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Two-step verification</dt>
            <dd className="font-medium">{user.mfa_enabled ? 'On' : 'Off'}</dd>
          </div>
        </dl>
        <p className="mt-6 text-sm text-slate-500">Your permissions:</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {user.permissions.map((permission) => (
            <li
              key={permission}
              className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-700"
            >
              {permission}
            </li>
          ))}
        </ul>
        <p className="mt-6 text-sm text-slate-400">The file dashboard arrives in the next step.</p>
      </section>
    </main>
  );
}
