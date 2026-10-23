import { Database, KeyRound, Link2, ShieldAlert, UsersRound } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';

import { getSystemOverview } from '../../api/adminReports';
import { getErrorMessage } from '../../api/client';
import { PageHeader, Panel, SeverityBadge } from '../../components/admin/AdminBits';
import { StackedBars } from '../../components/analytics/AnalyticsCharts';
import { ChartCard, SummaryCard } from '../../components/analytics/AnalyticsParts';
import { ErrorState, Loading } from '../../components/StateMessage';
import { presetRange, SERIES, shortDay } from '../../utils/charts';
import { formatBytes } from '../../utils/format';

const ACTIVITY_SERIES = [
  { key: 'uploads', label: 'Uploads', color: SERIES[0] },
  { key: 'downloads', label: 'Downloads', color: SERIES[1] },
];

/** Admin home: the whole platform at a glance (no file names or contents – privacy). */
export default function AdminDashboardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setError('');
    getSystemOverview(presetRange(30))
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading />;

  const { users, shares, keys } = data;
  const days = data.activity_by_day;
  const totals = ACTIVITY_SERIES.map((s) => ({
    ...s,
    value: days.reduce((n, d) => n + d[s.key], 0),
  }));
  const oldKeys = Object.entries(keys.keys_by_version).filter(
    ([version]) => Number(version) !== keys.active_version,
  );
  return (
    <div className="space-y-5">
      <PageHeader title="Admin Dashboard" text="The whole platform at a glance (last 30 days)." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          icon={UsersRound}
          tone="bg-blue-50 text-blue-600"
          label="Users"
          value={users.total}
          sub={`${users.active} active · ${users.inactive_30_days} inactive 30+ days`}
        />
        <SummaryCard
          icon={Database}
          tone="bg-green-50 text-green-600"
          label="Stored (encrypted)"
          value={formatBytes(data.total_bytes)}
          sub={`${data.total_files} files`}
        />
        <SummaryCard
          icon={Link2}
          tone="bg-violet-50 text-violet-600"
          label="Active shares"
          value={shares.links_active + shares.direct_active}
          sub={`${shares.links_active} links · ${shares.direct_active} people`}
        />
        <SummaryCard
          icon={ShieldAlert}
          tone="bg-red-50 text-red-600"
          label="Security events (7 days)"
          value={Object.values(data.events_last_7_days).reduce((a, b) => a + b, 0)}
          sub={`${data.events_last_7_days.high} high severity`}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <ChartCard
            title="Platform activity"
            legend={totals}
            empty={totals.every((t) => t.value === 0)}
            emptyText="No uploads or downloads in the last 30 days."
            table={{
              columns: [
                { key: 'day', label: 'Day' },
                ...ACTIVITY_SERIES.map((s) => ({ key: s.key, label: s.label })),
              ],
              rows: days.map((d) => ({ ...d, day: shortDay(d.date) })),
            }}
          >
            <StackedBars days={days} series={ACTIVITY_SERIES} />
          </ChartCard>
        </div>
        <div className="space-y-4">
          <Panel title="Accounts by role">
            <ul className="space-y-2 text-sm">
              {Object.entries(users.by_role).map(([role, count]) => (
                <li key={role} className="flex justify-between capitalize">
                  <span className="text-slate-600">{role}</span>
                  <span className="font-medium text-slate-900">{count}</span>
                </li>
              ))}
              <li className="flex justify-between border-t border-slate-100 pt-2">
                <span className="text-slate-600">Disabled</span>
                <span className="font-medium text-slate-900">{users.disabled}</span>
              </li>
            </ul>
            <Link
              to="/admin/users"
              className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline"
            >
              Manage users
            </Link>
          </Panel>
          <Panel title="Encryption keys">
            <p className="flex items-center gap-2 text-sm text-slate-700">
              <KeyRound className="size-4 text-blue-600" aria-hidden="true" />
              Active master key: <span className="font-medium">v{keys.active_version}</span>
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {oldKeys.length === 0
                ? 'All file keys use the active master key.'
                : `${oldKeys.reduce((n, [, c]) => n + c, 0)} file key(s) still on an older version – run rotate_keys.`}
            </p>
          </Panel>
          <Panel title="Security events (7 days)">
            <ul className="space-y-2">
              {Object.entries(data.events_last_7_days).map(([severity, count]) => (
                <li key={severity} className="flex items-center justify-between text-sm">
                  <SeverityBadge severity={severity} />
                  <span className="font-medium text-slate-900">{count}</span>
                </li>
              ))}
            </ul>
            <Link
              to="/admin/security"
              className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline"
            >
              Open Security Dashboard
            </Link>
          </Panel>
        </div>
      </div>
    </div>
  );
}
