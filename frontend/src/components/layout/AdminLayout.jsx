import {
  Activity,
  ArrowLeft,
  BellRing,
  FileBarChart,
  HardDrive,
  LayoutDashboard,
  Menu,
  ScrollText,
  ServerCog,
  Siren,
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
import NotificationBell from '../notifications/NotificationBell';
import UserMenu from './UserMenu';

// Admin panel menu, grouped like the Milestone 3 unified admin dashboard. Each page's data is protected on the server by a
// permission (user:read / audit:read); the menu only hides what the role can't open anyway.
const NAV = [
  {
    section: 'Overview',
    items: [
      {
        to: '/admin',
        label: 'Dashboard',
        icon: LayoutDashboard,
        end: true,
        permission: 'user:read',
      },
    ],
  },
  {
    section: 'Monitoring',
    items: [
      {
        to: '/admin/activity-monitoring',
        label: 'User activity',
        icon: Activity,
        permission: 'audit:read',
      },
      { to: '/admin/audit', label: 'Audit logs', icon: ScrollText, permission: 'audit:read' },
      {
        to: '/admin/security',
        label: 'Security monitoring',
        icon: ShieldAlert,
        permission: 'audit:read',
      },
      { to: '/admin/alerts', label: 'Suspicious activity', icon: Siren, permission: 'audit:read' },
    ],
  },
  {
    section: 'Reports & analytics',
    items: [
      {
        to: '/admin/reports',
        label: 'File activity reports',
        icon: FileBarChart,
        permission: 'audit:read',
      },
      {
        to: '/admin/storage',
        label: 'Storage analytics',
        icon: HardDrive,
        permission: 'audit:read',
      },
    ],
  },
  {
    section: 'Management',
    items: [
      { to: '/admin/users', label: 'User management', icon: UsersRound, permission: 'user:read' },
      {
        to: '/admin/notifications',
        label: 'Notifications',
        icon: BellRing,
        permission: 'audit:read',
      },
      { to: '/admin/system', label: 'System monitoring', icon: ServerCog, permission: 'user:read' },
    ],
  },
];

/** Dark admin frame around the admin pages. */
export default function AdminLayout() {
  const { can } = useAuth();
  const nav = NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => can(item.permission)),
  })).filter((group) => group.items.length > 0);
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
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-2" aria-label="Admin">
        {nav.map((group) => (
          <div key={group.section}>
            <p className="mb-1.5 px-3 text-[11px] font-semibold tracking-[0.08em] text-slate-500 uppercase">
              {group.section}
            </p>
            <div className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon, end }) => (
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
            </div>
          </div>
        ))}
      </nav>
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
          <NotificationBell />
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
