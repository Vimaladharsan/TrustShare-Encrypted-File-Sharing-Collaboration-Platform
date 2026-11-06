import {
  AlertTriangle,
  Bell,
  CalendarDays,
  CheckCircle2,
  Clock,
  FileText,
  HardDrive,
  MonitorSmartphone,
  Share2,
  ShieldAlert,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';

import { getAccountOverview } from '../api/account';
import { useAuth } from '../auth/useAuth';
import DeleteAccountCard from '../components/settings/DeleteAccountCard';
import DevicesTab from '../components/settings/DevicesTab';
import NotificationsTab from '../components/settings/NotificationsTab';
import ProfileTab from '../components/settings/ProfileTab';
import SecurityScoreCard from '../components/settings/SecurityScoreCard';
import SecurityTab from '../components/settings/SecurityTab';
import { formatBytes, formatDate, timeAgo } from '../utils/format';

const TABS = [
  { value: 'profile', label: 'Profile', icon: UserRound },
  { value: 'security', label: 'Security', icon: ShieldCheck },
  { value: 'devices', label: 'Devices', icon: MonitorSmartphone },
  { value: 'notifications', label: 'Notifications', icon: Bell },
  { value: 'account', label: 'Account', icon: AlertTriangle },
];
const ROLE_LABEL = { admin: 'Administrator', user: 'Standard user', guest: 'Guest' };

function initials(name) {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

/** My account: profile header, then Profile · Security · Devices · Account tabs (?tab=…). */
export default function SettingsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'profile';
  const [overview, setOverview] = useState(null); // security score + stats (one request)

  const loadOverview = useCallback(() => {
    getAccountOverview()
      .then(setOverview)
      .catch(() => setOverview(null)); // the page works without it
  }, []);

  // Reload when the tab changes: turning on two-step or signing out a device changes the score.
  useEffect(loadOverview, [loadOverview, tab, user.mfa_enabled]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <section className="card overflow-hidden">
        <div className="keep-colors relative h-28 bg-gradient-to-br from-blue-600 via-blue-600 to-indigo-700">
          <div className="pointer-events-none absolute -top-10 right-10 size-48 rounded-full bg-white/10 blur-2xl" />
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.08]"
            style={{
              backgroundImage:
                'linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)',
              backgroundSize: '28px 28px',
            }}
          />
        </div>
        <div className="flex flex-col gap-4 px-6 pb-6 sm:flex-row sm:items-end">
          <span className="relative z-10 -mt-10 grid size-20 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-2xl font-semibold text-white shadow-lg ring-4 ring-white">
            {initials(user.full_name)}
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-2xl font-semibold tracking-tight text-slate-950">
              {user.full_name}
            </h1>
            <p className="truncate text-sm text-slate-500">{user.email}</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs font-semibold">
            <Badge className="bg-blue-50 text-blue-700 ring-blue-600/15">
              {ROLE_LABEL[user.role] || user.role}
            </Badge>
            {user.is_email_verified ? (
              <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/15">
                <CheckCircle2 className="size-3" aria-hidden="true" /> Email verified
              </Badge>
            ) : (
              <Badge className="bg-amber-50 text-amber-700 ring-amber-600/15">
                Email not verified
              </Badge>
            )}
            {user.mfa_enabled ? (
              <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/15">
                <ShieldCheck className="size-3" aria-hidden="true" /> 2-step on
              </Badge>
            ) : (
              <Badge className="bg-amber-50 text-amber-700 ring-amber-600/15">
                <ShieldAlert className="size-3" aria-hidden="true" /> 2-step off
              </Badge>
            )}
            <Badge className="bg-slate-100 text-slate-600 ring-slate-500/10">
              <CalendarDays className="size-3" aria-hidden="true" /> Since{' '}
              {formatDate(user.created_at)}
            </Badge>
          </div>
        </div>
        {overview && <StatsStrip stats={overview.stats} />}
      </section>

      <nav
        className="flex [scrollbar-width:none] gap-1 overflow-x-auto overflow-y-hidden border-b border-slate-200"
        aria-label="Settings sections"
      >
        {TABS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            onClick={() => setParams({ tab: value })}
            aria-current={tab === value ? 'page' : undefined}
            className={`-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition ${
              tab === value
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800'
            }`}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </button>
        ))}
      </nav>

      {tab === 'profile' && overview && <SecurityScoreCard overview={overview} />}
      {tab === 'profile' && <ProfileTab />}
      {tab === 'security' && <SecurityTab />}
      {tab === 'devices' && <DevicesTab />}
      {tab === 'notifications' && <NotificationsTab />}
      {tab === 'account' && <DeleteAccountCard />}
    </div>
  );
}

/** Member since · files · storage · active shares · previous sign-in. */
function StatsStrip({ stats }) {
  const used = stats.storage_quota_bytes
    ? Math.min(100, Math.round((stats.storage_used_bytes / stats.storage_quota_bytes) * 100))
    : 0;
  const items = [
    { icon: CalendarDays, label: 'Member since', value: formatDate(stats.member_since) },
    { icon: FileText, label: 'Files', value: stats.files.toLocaleString('en-IN') },
    {
      icon: HardDrive,
      label: 'Storage',
      value: `${formatBytes(stats.storage_used_bytes)} of ${formatBytes(stats.storage_quota_bytes)}`,
      bar: used,
    },
    { icon: Share2, label: 'Active shares', value: stats.active_shares },
    {
      icon: Clock,
      label: 'Previous sign-in',
      value: stats.previous_sign_in ? timeAgo(stats.previous_sign_in.at) : '—',
      hint: stats.previous_sign_in?.device,
    },
  ];
  return (
    <dl className="grid grid-cols-2 gap-px border-t border-slate-100 bg-slate-100 sm:grid-cols-5">
      {items.map(({ icon: Icon, label, value, bar, hint }) => (
        <div key={label} className="bg-white px-5 py-3" title={hint}>
          <dt className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
            <Icon className="size-3.5" aria-hidden="true" /> {label}
          </dt>
          <dd className="mt-0.5 truncate text-sm font-semibold text-slate-900">{value}</dd>
          {bar !== undefined && (
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-blue-500"
                style={{ width: `${Math.max(bar, 2)}%` }}
              />
            </div>
          )}
          {hint && <dd className="truncate text-[11px] text-slate-400">{hint}</dd>}
        </div>
      ))}
    </dl>
  );
}

function Badge({ className, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 ring-1 ring-inset ${className}`}
    >
      {children}
    </span>
  );
}
