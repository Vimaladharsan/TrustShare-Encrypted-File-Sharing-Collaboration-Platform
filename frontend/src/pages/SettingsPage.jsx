import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  MonitorSmartphone,
  ShieldAlert,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { useSearchParams } from 'react-router';

import { useAuth } from '../auth/useAuth';
import DeleteAccountCard from '../components/settings/DeleteAccountCard';
import DevicesTab from '../components/settings/DevicesTab';
import ProfileTab from '../components/settings/ProfileTab';
import SecurityTab from '../components/settings/SecurityTab';
import { formatDate } from '../utils/format';

const TABS = [
  { value: 'profile', label: 'Profile', icon: UserRound },
  { value: 'security', label: 'Security', icon: ShieldCheck },
  { value: 'devices', label: 'Devices', icon: MonitorSmartphone },
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

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <section className="card overflow-hidden">
        <div className="relative h-28 bg-gradient-to-br from-blue-600 via-blue-600 to-indigo-700">
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
          <span className="-mt-10 grid size-20 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-2xl font-semibold text-white shadow-lg ring-4 ring-white">
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

      {tab === 'profile' && <ProfileTab />}
      {tab === 'security' && <SecurityTab />}
      {tab === 'devices' && <DevicesTab />}
      {tab === 'account' && <DeleteAccountCard />}
    </div>
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
