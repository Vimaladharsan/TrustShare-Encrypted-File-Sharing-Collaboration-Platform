import { FolderOpen, Search, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate, useSearchParams } from 'react-router';

import { getUsage } from '../../api/files';
import Logo from '../Logo';
import StorageMeter from './StorageMeter';
import UserMenu from './UserMenu';

const NAV = [
  { to: '/files', label: 'My Files', icon: FolderOpen },
  { to: '/trash', label: 'Trash', icon: Trash2 },
];

/** The workspace frame: sidebar + top bar around every dashboard page (<Outlet />). */
export default function DashboardLayout() {
  const [usage, setUsage] = useState(null);

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
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <Logo className="mb-6 px-2" />
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
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
        {/* Mobile: the sidebar is hidden, so show the two links here instead. */}
        <nav className="flex gap-2 border-b border-slate-200 bg-white px-4 py-2 md:hidden">
          {NAV.map(({ to, label }) => (
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
