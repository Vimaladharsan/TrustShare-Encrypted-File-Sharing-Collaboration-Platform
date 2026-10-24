import {
  ArrowRight,
  BarChart3,
  CloudUpload,
  Database,
  Download,
  FolderOpen,
  Inbox,
  KeyRound,
  Lock,
  Share2,
  ShieldCheck,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router';

import { getAnalytics, getRecentFiles } from '../api/analytics';
import { getErrorMessage } from '../api/client';
import { listReceivedShares } from '../api/shares';
import { useAuth } from '../auth/useAuth';
import { SummaryCard } from '../components/analytics/AnalyticsParts';
import FileIcon from '../components/files/FileIcon';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import { presetRange } from '../utils/charts';
import { formatBytes } from '../utils/format';

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

/** Home after login: a welcome banner, the last 30 days at a glance, recent files, shortcuts. */
export default function DashboardPage() {
  const { user, can } = useAuth();
  const [state, setState] = useState({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getAnalytics(presetRange(30)), getRecentFiles(), listReceivedShares()])
      .then(([analytics, recent, received]) => {
        if (!cancelled) setState({ status: 'ready', analytics, recent, received });
      })
      .catch((err) => {
        if (!cancelled) setState({ status: 'error', error: getErrorMessage(err) });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const firstName = user.full_name.split(' ')[0];
  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600 via-blue-600 to-indigo-700 p-6 text-white shadow-lg shadow-blue-600/20 sm:p-8">
        {/* Decorative light blobs and a subtle grid – purely visual. */}
        <div className="pointer-events-none absolute -top-24 -right-16 size-72 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/3 size-72 rounded-full bg-indigo-400/30 blur-3xl" />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs font-medium ring-1 ring-white/20 backdrop-blur">
              <Lock className="size-3" aria-hidden="true" /> AES-256 encryption active
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">
              {greeting()}, {firstName}
            </h1>
            <p className="mt-1.5 max-w-xl text-sm text-blue-100">
              Every file you store is encrypted with its own AES-256 key, and every share is checked
              on each access. Here is your last 30 days.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {can('file:upload') && (
              <Link
                to="/files"
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-white px-4 text-sm font-semibold text-blue-700 shadow-sm transition hover:bg-blue-50"
              >
                <CloudUpload className="size-4" aria-hidden="true" /> Upload files
              </Link>
            )}
            <Link
              to="/analytics"
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-white/10 px-4 text-sm font-semibold text-white ring-1 ring-white/25 transition hover:bg-white/20"
            >
              <BarChart3 className="size-4" aria-hidden="true" /> View analytics
            </Link>
          </div>
        </div>
      </section>

      {state.status === 'loading' && <Loading rows={3} />}
      {state.status === 'error' && (
        <ErrorState message={state.error} onRetry={() => setAttempt((n) => n + 1)} />
      )}
      {state.status === 'ready' && (
        <Overview {...state} canUpload={can('file:upload')} canShare={can('share:create')} />
      )}
    </div>
  );
}

function Overview({ analytics, recent, received, canUpload, canShare }) {
  const s = analytics.summary;
  const shortcuts = [
    canUpload && {
      to: '/files',
      icon: FolderOpen,
      tone: 'bg-blue-50 text-blue-600',
      label: 'My Files',
      text: 'Upload and organise',
    },
    {
      to: '/shared-with-me',
      icon: Inbox,
      tone: 'bg-emerald-50 text-emerald-600',
      label: 'Shared with me',
      text: `${received.length} file${received.length === 1 ? '' : 's'} waiting`,
    },
    canShare && {
      to: '/shared-by-me',
      icon: Share2,
      tone: 'bg-violet-50 text-violet-600',
      label: 'Shared by me',
      text: 'Links and people',
    },
    {
      to: '/security',
      icon: ShieldCheck,
      tone: 'bg-amber-50 text-amber-600',
      label: 'Security',
      text: 'How your files are protected',
    },
  ].filter(Boolean);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          icon={Database}
          tone="bg-blue-50 text-blue-600"
          label="Storage used"
          value={formatBytes(s.storage_used_bytes)}
          sub={`of ${formatBytes(s.quota_bytes)}`}
        />
        <SummaryCard
          icon={CloudUpload}
          tone="bg-emerald-50 text-emerald-600"
          label="Uploads"
          value={s.uploads.value}
          sub="last 30 days"
          metric={s.uploads}
        />
        <SummaryCard
          icon={Download}
          tone="bg-violet-50 text-violet-600"
          label="Downloads"
          value={s.downloads.value}
          sub="of your files"
          metric={s.downloads}
        />
        <SummaryCard
          icon={Share2}
          tone="bg-rose-50 text-rose-600"
          label="Shares"
          value={s.shares.value}
          sub="last 30 days"
          metric={s.shares}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card min-w-0 lg:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-slate-950">Recent files</h2>
              <p className="text-xs text-slate-500">What you worked on lately</p>
            </div>
            <Link
              to="/recent"
              className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              View all <ArrowRight className="size-3.5" aria-hidden="true" />
            </Link>
          </div>
          {recent.length === 0 ? (
            <Empty
              icon={FolderOpen}
              title="No recent files yet"
              text="Upload or open a file and it shows up here."
            />
          ) : (
            <ul className="divide-y divide-slate-100 px-2 py-1">
              {recent.slice(0, 6).map(({ file, last_activity_at: at }) => (
                <li
                  key={file.id}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition hover:bg-slate-50"
                >
                  <FileIcon category={file.category} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-800">
                      {file.name}
                    </span>
                    <span className="block text-xs text-slate-400">
                      {file.extension.toUpperCase()} · {formatBytes(file.size_bytes)}
                    </span>
                  </span>
                  <span className="hidden text-xs text-slate-500 sm:block">
                    {new Date(at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="space-y-4">
          <section className="card p-2">
            <h2 className="px-3 pt-3 pb-2 font-semibold text-slate-950">Shortcuts</h2>
            <ul>
              {shortcuts.map(({ to, icon: Icon, tone, label, text }) => (
                <li key={to}>
                  <Link
                    to={to}
                    className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-slate-50"
                  >
                    <span className={`grid size-9 place-items-center rounded-lg ${tone}`}>
                      <Icon className="size-[18px]" aria-hidden="true" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-slate-800">{label}</span>
                      <span className="block text-xs text-slate-500">{text}</span>
                    </span>
                    <ArrowRight
                      className="size-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500"
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
          <section className="shadow-card flex items-start gap-3 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10 ring-1 ring-white/15">
              <KeyRound className="size-[18px]" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-semibold">Your keys never leave the server</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-300">
                File keys are stored only in wrapped form and rotated without re-uploading. Not even
                admins can open your files.
              </p>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
