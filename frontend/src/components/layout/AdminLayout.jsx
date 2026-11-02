import {
  Activity,
  ArrowLeft,
  BellRing,
  ChevronRight,
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
import { useLayoutEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router';

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

// Console chrome colours: fixed (not theme tokens), so the frame looks the same on every page.
const RAIL = 'border-[#1a2330] bg-[#070b11]';

/** The nav entry for the current address (longest match), for the header's breadcrumb. */
function currentEntry(pathname) {
  let best = null;
  for (const group of NAV) {
    for (const item of group.items) {
      const match = item.end ? pathname === item.to : pathname.startsWith(item.to);
      if (match && (!best || item.to.length > best.item.to.length)) best = { group, item };
    }
  }
  return best;
}

/**
 * The admin console: a dark operations-console frame around the admin pages, deliberately unlike
 * the light user workspace. While it is open, <html> gets the `admin-console` class, which
 * switches the whole colour palette to the console theme (index.css) – pages, dialogs and menus.
 */
export default function AdminLayout() {
  const { can } = useAuth();
  const { pathname } = useLocation();
  const nav = NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => can(item.permission)),
  })).filter((group) => group.items.length > 0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const here = currentEntry(pathname);

  // Before the first paint, so the workspace's light theme never flashes inside the console.
  useLayoutEffect(() => {
    document.documentElement.classList.add('admin-console');
    return () => document.documentElement.classList.remove('admin-console');
  }, []);

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
    <div className={`flex h-full flex-col border-r ${RAIL} text-[#8e9cb0]`}>
      <div className={`flex h-16 shrink-0 items-center gap-2.5 border-b ${RAIL} px-5`}>
        <Logo />
        <span className="rounded border border-teal-400/30 bg-teal-400/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wider text-teal-300 uppercase">
          Console
        </span>
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5" aria-label="Admin">
        {nav.map((group) => (
          <div key={group.section}>
            <p className="mb-2 px-3 font-mono text-[10px] font-medium tracking-[0.14em] text-[#56657a] uppercase">
              {group.section}
            </p>
            <div className="space-y-px">
              {group.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={() => setDrawerOpen(false)}
                  className={({ isActive }) =>
                    `group relative flex items-center gap-3 rounded-md px-3 py-[7px] text-[13px] font-medium transition ${
                      isActive
                        ? 'bg-teal-400/[0.08] text-teal-200'
                        : 'hover:bg-white/[0.04] hover:text-[#e8edf3]'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute inset-y-1.5 -left-3 w-[3px] rounded-r bg-teal-400 shadow-[0_0_12px_rgb(45_212_191/0.6)]" />
                      )}
                      <Icon
                        className={`size-4 ${isActive ? 'text-teal-300' : 'text-[#56657a] group-hover:text-[#a6b2c2]'}`}
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
      <div className={`mt-auto border-t ${RAIL} p-3`}>
        <div className="mb-2 rounded-md border border-[#1a2330] bg-[#0b1017] p-3 text-[11px] leading-relaxed">
          <p className="mb-1 flex items-center gap-1.5 font-mono text-[10px] font-semibold tracking-wider text-teal-300 uppercase">
            <ShieldCheck className="size-3.5" aria-hidden="true" /> Privacy by design
          </p>
          Admins see accounts, sizes and security events – never the names or contents of
          users&apos; files.
        </div>
        <NavLink
          to="/dashboard"
          className="flex items-center gap-2 rounded-md px-3 py-2 text-[13px] font-medium transition hover:bg-white/[0.04] hover:text-[#e8edf3]"
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
            className="animate-fade-in absolute inset-0 bg-black/60 backdrop-blur-[2px]"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="animate-slide-in shadow-pop absolute inset-y-0 left-0 w-72">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="absolute top-4 right-3 z-10 rounded-md p-1.5 text-[#8e9cb0] hover:bg-white/10 hover:text-[#e8edf3]"
              aria-label="Close menu"
            >
              <X className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-[#0b1017]/85 px-4 backdrop-blur-md sm:px-6">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="-ml-1 rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 lg:hidden"
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </button>
          <nav
            className="flex min-w-0 items-center gap-1.5 font-mono text-xs text-slate-500"
            aria-label="Breadcrumb"
          >
            <span className="hidden sm:inline">admin</span>
            {here && (
              <>
                <ChevronRight
                  className="hidden size-3.5 text-slate-300 sm:inline"
                  aria-hidden="true"
                />
                <span className="hidden truncate md:inline">
                  {here.group.section.toLowerCase()}
                </span>
                <ChevronRight
                  className="hidden size-3.5 text-slate-300 md:inline"
                  aria-hidden="true"
                />
                <span className="truncate font-semibold text-slate-900">{here.item.label}</span>
              </>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-md border border-slate-200 bg-slate-100/60 px-2.5 py-1 font-mono text-[11px] text-slate-500 xl:flex">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex size-2 rounded-full bg-emerald-400" />
              </span>
              Secure session · RBAC enforced server-side
            </div>
            <NotificationBell />
            <UserMenu />
          </div>
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
