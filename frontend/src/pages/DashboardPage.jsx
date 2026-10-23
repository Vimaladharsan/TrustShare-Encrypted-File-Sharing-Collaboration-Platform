import {
  BarChart3,
  CloudUpload,
  Database,
  Download,
  FolderOpen,
  Inbox,
  Share2,
  ShieldCheck,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router';

import { getAnalytics, getRecentFiles } from '../api/analytics';
import { getErrorMessage } from '../api/client';
import { listReceivedShares } from '../api/shares';
import { SummaryCard } from '../components/analytics/AnalyticsParts';
import { ErrorState, Loading } from '../components/StateMessage';
import { useAuth } from '../auth/useAuth';
import { presetRange } from '../utils/charts';
import { fileIcon, formatBytes } from '../utils/format';

/** Home after login: the last 30 days at a glance, recent files and shortcuts. */
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
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Welcome back, {firstName}</h1>
        <p className="text-sm text-slate-500">Here is what happened in the last 30 days.</p>
      </div>

      {state.status === 'loading' && <Loading />}
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
    canUpload && { to: '/files', icon: FolderOpen, label: 'My Files', text: 'Upload and organise' },
    {
      to: '/shared-with-me',
      icon: Inbox,
      label: 'Shared with me',
      text: `${received.length} file(s)`,
    },
    canShare && {
      to: '/shared-by-me',
      icon: Share2,
      label: 'Shared by me',
      text: 'Links and people',
    },
    { to: '/analytics', icon: BarChart3, label: 'File Analytics', text: 'Charts and reports' },
    { to: '/security', icon: ShieldCheck, label: 'Security', text: 'How your files are protected' },
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
          tone="bg-green-50 text-green-600"
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
        <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Recent files</h2>
            <Link to="/recent" className="text-sm font-medium text-blue-600 hover:underline">
              View all
            </Link>
          </div>
          {recent.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No recent files yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {recent.slice(0, 6).map(({ file, last_activity_at: at }) => {
                const { Icon, color } = fileIcon(file.category);
                return (
                  <li key={file.id} className="flex items-center gap-3 py-2 text-sm">
                    <Icon className={`size-4 shrink-0 ${color}`} aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate text-slate-800">{file.name}</span>
                    <span className="text-xs text-slate-500">{formatBytes(file.size_bytes)}</span>
                    <span className="hidden w-28 text-right text-xs text-slate-500 sm:block">
                      {new Date(at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-slate-900">Shortcuts</h2>
          <ul className="space-y-1">
            {shortcuts.map(({ to, icon: Icon, label, text }) => (
              <li key={to}>
                <Link
                  to={to}
                  className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-slate-50"
                >
                  <Icon className="size-4 text-blue-600" aria-hidden="true" />
                  <span className="text-sm font-medium text-slate-800">{label}</span>
                  <span className="ml-auto text-xs text-slate-500">{text}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
