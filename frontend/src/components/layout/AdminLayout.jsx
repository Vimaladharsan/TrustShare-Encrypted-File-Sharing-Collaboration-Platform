import {
  Activity,
  ArrowLeft,
  FolderLock,
  LayoutDashboard,
  Link2,
  ServerCog,
  ShieldAlert,
  ShieldOff,
  UsersRound,
} from 'lucide-react';
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

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-slate-900 p-4 text-slate-300 md:flex">
        <div className="mb-6 rounded-lg bg-white px-2 py-1.5">
          <Logo />
        </div>
        <p className="mb-2 px-3 text-xs font-semibold tracking-wider text-slate-500 uppercase">
          Admin panel
        </p>
        <nav className="flex flex-col gap-1">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-blue-600 text-white' : 'hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <NavLink
          to="/dashboard"
          className="mt-auto flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-800 hover:text-white"
        >
          <ArrowLeft className="size-4" aria-hidden="true" /> Back to my workspace
        </NavLink>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4">
          <span className="text-sm font-semibold text-slate-700 md:hidden">Admin panel</span>
          <span className="hidden text-sm text-slate-500 md:block">
            Administration – access is checked on the server for every request
          </span>
          <UserMenu />
        </header>
        <nav className="flex gap-2 overflow-x-auto border-b border-slate-200 bg-white px-4 py-2 whitespace-nowrap md:hidden">
          {nav.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `rounded-full px-3 py-1 text-sm ${isActive ? 'bg-blue-50 text-blue-700' : 'text-slate-600'}`
              }
            >
              {label}
            </NavLink>
          ))}
          <NavLink to="/dashboard" className="rounded-full px-3 py-1 text-sm text-slate-600">
            My workspace
          </NavLink>
        </nav>
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
