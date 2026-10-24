import { Menu, Search, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate, useSearchParams } from 'react-router';

import { getUsage } from '../../api/files';
import Sidebar from './Sidebar';
import UserMenu from './UserMenu';
import VerifyEmailBanner from './VerifyEmailBanner';

/** The workspace frame: sidebar + top bar around every dashboard page (<Outlet />). */
export default function DashboardLayout() {
  const [usage, setUsage] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  const refreshUsage = useCallback(() => {
    getUsage()
      .then(setUsage)
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshUsage();
  }, [refreshUsage]);

  // Close the mobile drawer whenever the page changes.
  const [lastPath, setLastPath] = useState(location.pathname);
  if (lastPath !== location.pathname) {
    setLastPath(location.pathname);
    setDrawerOpen(false);
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-slate-200/80 bg-white lg:block">
        <Sidebar usage={usage} />
      </aside>

      {/* Mobile / tablet: the same sidebar slides in from the left. */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
        >
          <div
            className="animate-fade-in absolute inset-0 bg-slate-950/40 backdrop-blur-[2px]"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="animate-slide-in shadow-pop absolute inset-y-0 left-0 w-72 bg-white">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="absolute top-4 right-3 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="Close menu"
            >
              <X className="size-5" />
            </button>
            <Sidebar usage={usage} onNavigate={() => setDrawerOpen(false)} />
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
          <SearchBox />
          <UserMenu />
        </header>
        <VerifyEmailBanner />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet context={{ refreshUsage }} />
          </div>
        </main>
      </div>
    </div>
  );
}

function SearchBox() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get('q') || '');
  const inputRef = useRef(null);

  // Ctrl+K / ⌘K or "/" jumps to search from anywhere (but not while typing in a field).
  useEffect(() => {
    const onKey = (event) => {
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
      if (
        (event.key === 'k' && (event.ctrlKey || event.metaKey)) ||
        (event.key === '/' && !typing)
      ) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function handleSubmit(event) {
    event.preventDefault();
    const q = query.trim();
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/files');
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl flex-1" role="search">
      <label className="group relative block">
        <span className="sr-only">Search files</span>
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400 group-focus-within:text-blue-600" />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your files…"
          className="w-full rounded-xl border border-transparent bg-slate-100/80 py-2 pr-16 pl-9 text-sm transition placeholder:text-slate-400 hover:bg-slate-100 focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-500/15 focus:outline-none"
        />
        <kbd className="pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 rounded-md border border-slate-200 bg-white px-1.5 py-0.5 font-sans text-[10px] font-medium text-slate-400 shadow-xs sm:block">
          Ctrl K
        </kbd>
      </label>
    </form>
  );
}
