import {
  BarChart3,
  Clock,
  FolderOpen,
  HardDrive,
  History,
  Inbox,
  LayoutDashboard,
  Settings,
  Share2,
  ShieldCheck,
  ShieldEllipsis,
  Star,
  Trash2,
} from 'lucide-react';
import { NavLink } from 'react-router';

import { useAuth } from '../../auth/useAuth';
import Logo from '../Logo';
import StorageMeter from './StorageMeter';

// Sidebar sections (mentor's layout). Items with `permission` are shown only to roles that have
// it – the API checks the permission again, hiding a link is just a convenience.
const SECTIONS = [
  {
    label: 'Workspace',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/files', label: 'My Files', icon: FolderOpen },
      { to: '/shared-with-me', label: 'Shared with me', icon: Inbox },
      { to: '/shared-by-me', label: 'Shared by me', icon: Share2, permission: 'share:create' },
      { to: '/recent', label: 'Recent', icon: Clock },
      { to: '/favorites', label: 'Favorites', icon: Star },
      { to: '/trash', label: 'Trash', icon: Trash2 },
    ],
  },
  {
    label: 'Insights',
    items: [
      { to: '/storage', label: 'Storage', icon: HardDrive },
      { to: '/analytics', label: 'File Analytics', icon: BarChart3 },
      { to: '/activity', label: 'Activity Logs', icon: History },
      { to: '/security', label: 'Security', icon: ShieldCheck },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
  {
    label: 'Administration',
    items: [{ to: '/admin', label: 'Admin panel', icon: ShieldEllipsis, permission: 'user:read' }],
  },
];

/** The workspace sidebar – used on desktop and inside the mobile drawer. */
export default function Sidebar({ usage, onNavigate }) {
  const { can } = useAuth();
  const sections = SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => !item.permission || can(item.permission)),
  })).filter((section) => section.items.length > 0);

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 shrink-0 items-center px-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-2" aria-label="Main">
        {sections.map((section) => (
          <div key={section.label}>
            <p className="eyebrow mb-1.5 px-3">{section.label}</p>
            <ul className="space-y-0.5">
              {section.items.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      `group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                        isActive
                          ? 'bg-blue-50 text-blue-700'
                          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span className="absolute top-1/2 -left-3 h-5 w-1 -translate-y-1/2 rounded-r-full bg-blue-600" />
                        )}
                        <Icon
                          className={`size-[18px] ${isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'}`}
                          aria-hidden="true"
                        />
                        {label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="shrink-0 p-3">
        <StorageMeter usage={usage} />
      </div>
    </div>
  );
}
