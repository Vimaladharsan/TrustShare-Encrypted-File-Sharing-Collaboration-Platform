import { ChevronDown, LogOut, Settings, ShieldCheck, ShieldEllipsis } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import { useAuth } from '../../auth/useAuth';

const ROLE_LABEL = { admin: 'Administrator', user: 'Standard user', guest: 'Guest' };

function initialsOf(name) {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

/** Avatar, name and role; opens a menu with the account details, shortcuts and Log out. */
export default function UserMenu() {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => ref.current && !ref.current.contains(event.target) && setOpen(false);
    const onKey = (event) => event.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  async function handleLogout() {
    await logout();
    toast.success('You have been logged out.');
    navigate('/login');
  }

  function go(path) {
    setOpen(false);
    navigate(path);
  }

  const items = [
    { label: 'Settings', icon: Settings, path: '/settings' },
    { label: 'Security', icon: ShieldCheck, path: '/security' },
    can('user:read') && { label: 'Admin panel', icon: ShieldEllipsis, path: '/admin' },
  ].filter(Boolean);

  return (
    <div className="relative ml-auto" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2.5 rounded-xl p-1 pr-2 transition hover:bg-slate-100"
        aria-label="Account menu"
        aria-expanded={open}
      >
        <Avatar name={user.full_name} />
        <span className="hidden text-left leading-tight md:block">
          <span className="block max-w-40 truncate text-sm font-semibold text-slate-900">
            {user.full_name}
          </span>
          <span className="block text-xs text-slate-500">{ROLE_LABEL[user.role] || user.role}</span>
        </span>
        <ChevronDown
          className={`hidden size-4 text-slate-400 transition md:block ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>
      {open && (
        <div className="animate-pop-in shadow-pop absolute right-0 z-40 mt-2 w-64 overflow-hidden rounded-xl bg-white ring-1 ring-slate-900/10">
          <div className="flex items-center gap-3 border-b border-slate-100 bg-slate-50/70 p-4">
            <Avatar name={user.full_name} large />
            <div className="min-w-0">
              <p className="truncate font-semibold text-slate-900">{user.full_name}</p>
              <p className="truncate text-xs text-slate-500">{user.email}</p>
            </div>
          </div>
          <div className="p-1.5">
            {items.map(({ label, icon: Icon, path }) => (
              <button
                key={path}
                type="button"
                onClick={() => go(path)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-slate-700 transition hover:bg-slate-100 hover:text-slate-950"
              >
                <Icon className="size-4 text-slate-400" aria-hidden="true" />
                {label}
              </button>
            ))}
            <div className="mx-1 my-1 h-px bg-slate-100" />
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-red-600 transition hover:bg-red-50"
            >
              <LogOut className="size-4" aria-hidden="true" />
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Avatar({ name, large = false }) {
  return (
    <span
      className={`grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 font-semibold text-white shadow-sm ring-2 ring-white ${
        large ? 'size-10 text-sm' : 'size-9 text-xs'
      }`}
      aria-hidden="true"
    >
      {initialsOf(name)}
    </span>
  );
}
