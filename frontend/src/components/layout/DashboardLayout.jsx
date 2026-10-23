import {
  BarChart3,
  Clock,
  FolderOpen,
  HardDrive,
  History,
  Inbox,
  LayoutDashboard,
  Search,
  Settings,
  Share2,
  ShieldCheck,
  Star,
  Trash2,
  UsersRound,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate, useSearchParams } from 'react-router';

import { getUsage } from '../../api/files';
import { useAuth } from '../../auth/useAuth';
import Logo from '../Logo';
import StorageMeter from './StorageMeter';
import UserMenu from './UserMenu';
import VerifyEmailBanner from './VerifyEmailBanner';

// Sidebar sections (mentor's layout). Items with `permission` are shown only to roles that have
// it – the API checks the permission again, hiding a link is just a convenience.
const NAV = [
  [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/files', label: 'My Files', icon: FolderOpen },
    { to: '/shared-with-me', label: 'Shared with me', icon: Inbox },
    { to: '/shared-by-me', label: 'Shared by me', icon: Share2, permission: 'share:create' },
    { to: '/recent', label: 'Recent', icon: Clock },
    { to: '/favorites', label: 'Favorites', icon: Star },
    { to: '/trash', label: 'Trash', icon: Trash2 },
  ],
  [
    { to: '/storage', label: 'Storage', icon: HardDrive },
    { to: '/analytics', label: 'File Analytics', icon: BarChart3 },
    { to: '/activity', label: 'Activity Logs', icon: History },
    { to: '/security', label: 'Security', icon: ShieldCheck },
    { to: '/settings', label: 'Settings', icon: Settings },
  ],
  [{ to: '/admin/users', label: 'Users', icon: UsersRound, permission: 'user:read' }],
];

/** The workspace frame: sidebar + top bar around every dashboard page (<Outlet />). */
export default function DashboardLayout() {
  const { can } = useAuth();
  const [usage, setUsage] = useState(null);
  const sections = NAV.map((items) =>
    items.filter((item) => !item.permission || can(item.permission)),
  ).filter((items) => items.length > 0);
  const nav = sections.flat();

  const refreshUsage = useCallback(() => {
    getUsage()
      .then(setUsage)
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshUsage();
  }, [refreshUsage]);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <Logo className="mb-6 px-2" />
        <nav className="flex flex-col gap-1 overflow-y-auto">
          {sections.map((items, index) => (
            <div
              key={items[0].to}
              className={`flex flex-col gap-1 ${index ? 'mt-2 border-t border-slate-100 pt-3' : ''}`}
            >
              {items.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${
                      isActive ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  <Icon className="size-4" aria-hidden="true" />
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="mt-auto">
          <StorageMeter usage={usage} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4">
          <SearchBox />
          <UserMenu />
        </header>
        <VerifyEmailBanner />
        {/* Mobile: the sidebar is hidden, so show its links here instead. */}
        <nav className="flex gap-2 overflow-x-auto border-b border-slate-200 bg-white px-4 py-2 whitespace-nowrap md:hidden">
          {nav.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `rounded-full px-3 py-1 text-sm ${isActive ? 'bg-blue-50 text-blue-700' : 'text-slate-600'}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 p-4 sm:p-6">
          <Outlet context={{ refreshUsage }} />
        </main>
      </div>
    </div>
  );
}

function SearchBox() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get('q') || '');

  function handleSubmit(event) {
    event.preventDefault();
    const q = query.trim();
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/files');
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl flex-1" role="search">
      <label className="relative block">
        <span className="sr-only">Search files</span>
        <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search files"
          className="w-full rounded-full border-none bg-slate-100 py-2 pr-4 pl-9 text-sm focus:bg-white focus:ring-2 focus:ring-blue-100 focus:outline-none"
        />
      </label>
    </form>
  );
}
