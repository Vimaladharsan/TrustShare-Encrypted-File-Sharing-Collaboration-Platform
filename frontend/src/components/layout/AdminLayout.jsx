import {
  Activity,
  ArrowLeft,
  FolderLock,
  LayoutDashboard,
  Link2,
  Menu,
  ServerCog,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  UsersRound,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router';

import { useAuth } from '../../auth/useAuth';
import Logo from '../Logo';
import { Empty } from '../StateMessage';
import UserMenu from './UserMenu';

// Admin panel menu (mentor's mockup). Each page's data is protected on the server by a
// permission (user:read / audit:read); the menu only hides what the role can't open anyway.
const NAV = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true, permission: 'user:read' },
  { to: '/admin/users', label: 'User management', icon: UsersRound, permission: 'user:read' },
  { to: '/admin/storage', label: 'File management', icon: FolderLock, permission: 'user:read' },
  { to: '/admin/sharing', label: 'Sharing reports', icon: Link2, permission: 'user:read' },
  {
    to: '/admin/security',
    label: 'Security dashboard',
    icon: ShieldAlert,
    permission: 'audit:read',
  },
  { to: '/admin/system', label: 'System monitoring', icon: ServerCog, permission: 'user:read' },
  { to: '/admin/activity', label: 'Activity logs', icon: Activity, permission: 'audit:read' },
];

/** Dark admin frame around the admin pages. */
export default function AdminLayout() {
  const { can } = useAuth();
  const nav = NAV.filter((item) => can(item.permission));
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (!can('user:read')) {
    // Someone typed /admin… without the role: the API would refuse anyway (403).
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50">
        <Empty
          icon={ShieldOff}
          title="Admins only"
          text="You don't have access to the admin panel."
        >
          <NavLink to="/dashboard" className="text-sm font-medium text-blue-600 hover:underline">
            Back to your workspace
          </NavLink>
        </Empty>
      </main>
    );
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 text-slate-400">
      <div className="flex h-16 shrink-0 items-center px-5">
        <Logo variant="light" />
      </div>
      <div className="px-3">
        <p className="mb-1.5 px-3 text-[11px] font-semibold tracking-[0.08em] text-slate-500 uppercase">
          Admin panel
        </p>
        <nav className="space-y-0.5" aria-label="Admin">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setDrawerOpen(false)}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive ? 'bg-white/10 text-white' : 'hover:bg-white/5 hover:text-slate-100'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute top-1/2 -left-3 h-5 w-1 -translate-y-1/2 rounded-r-full bg-blue-400" />
                  )}
                  <Icon
                    className={`size-[18px] ${isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'}`}
                    aria-hidden="true"
                  />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="mt-auto p-3">
        <div className="mb-3 rounded-xl bg-white/5 p-3 text-xs leading-relaxed text-slate-400 ring-1 ring-white/10">
          <span className="font-semibold text-slate-200">Privacy by design.</span> Admins see
          accounts, sizes and security events – never the contents of users&apos; files.
        </div>
        <NavLink
          to="/dashboard"
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition hover:bg-white/5 hover:text-white"
        >
          <ArrowLeft className="size-4" aria-hidden="true" /> Back to my workspace
        </NavLink>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 lg:block">{sidebar}</aside>

      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
        >
          <div
            className="animate-fade-in absolute inset-0 bg-slate-950/50 backdrop-blur-[2px]"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="animate-slide-in shadow-pop absolute inset-y-0 left-0 w-72">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="absolute top-4 right-3 z-10 rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
              aria-label="Close menu"
            >
              <X className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200/70 bg-white/80 px-4 backdrop-blur-md sm:px-6">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="-ml-1 rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </button>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white">
            <ShieldCheck className="size-3.5 text-blue-300" aria-hidden="true" /> Admin
          </span>
          <span className="hidden text-sm text-slate-500 xl:block">
            Every request is permission-checked on the server
          </span>
          <UserMenu />
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
