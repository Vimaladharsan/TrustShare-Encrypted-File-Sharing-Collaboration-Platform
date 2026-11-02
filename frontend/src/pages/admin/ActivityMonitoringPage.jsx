import { Pause, Play, Radio } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { getErrorMessage } from '../../api/client';
import { getActivities, getActivitySummary, openActivityStream } from '../../api/monitoring';
import { PageHeader, Panel } from '../../components/admin/AdminBits';
import { DataTable, FilterBar, Pager, StatusBadge } from '../../components/admin/MonitoringBits';
import { humanize } from '../../utils/monitoring';
import Button from '../../components/Button';
import { ErrorState, Loading } from '../../components/StateMessage';
import { presetRange } from '../../utils/charts';

const LIMIT = 25;

/** User Activity Monitoring: what is happening right now, live, plus counts by activity type. */
export default function ActivityMonitoringPage() {
  const [filters, setFilters] = useState({ offset: 0 });
  const [summary, setSummary] = useState(null);
  const [feed, setFeed] = useState(null);
  const [error, setError] = useState('');
  const [paused, setPaused] = useState(false);
  const [live, setLive] = useState(false);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const load = useCallback(async () => {
    setError('');
    try {
      const [s, f] = await Promise.all([
        getActivitySummary(presetRange(7)),
        getActivities({ ...filters, limit: LIMIT }),
      ]);
      setSummary(s);
      setFeed(f);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const matches = useCallback(
    (item) =>
      (!filters.activity_type || item.activity_type === filters.activity_type) &&
      (!filters.status || item.status === filters.status) &&
      (!filters.user_id || item.user_id === filters.user_id),
    [filters],
  );

  // Live: new activity appears at the top (first page only, unless paused).
  useEffect(() => {
    if (filters.offset || filters.q) return undefined;
    const stop = openActivityStream((event, data) => {
      if (event === 'ready') setLive(true);
      if (event !== 'activity' || pausedRef.current || !matches(data)) return;
      setFeed((current) =>
        current
          ? {
              items: [{ ...data, isNew: true }, ...current.items].slice(0, LIMIT),
              total: current.total + 1,
            }
          : current,
      );
    });
    return () => {
      stop();
      setLive(false);
    };
  }, [filters.offset, filters.q, matches]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!summary || !feed) return <Loading />;
  return (
    <div className="space-y-5">
      <PageHeader
        title="User activity monitoring"
        text="Every sign-in, upload, download, share and denied attempt – recorded automatically. File names are never shown."
      >
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
              live && !paused ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
            }`}
          >
            <Radio className="size-3.5" aria-hidden="true" />
            {paused ? 'Paused' : live ? 'Live' : 'Connecting…'}
          </span>
          <Button variant="secondary" size="sm" onClick={() => setPaused((p) => !p)}>
            {paused ? <Play className="size-4" /> : <Pause className="size-4" />}
            {paused ? 'Resume' : 'Pause'}
          </Button>
        </div>
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Activities (7 days)" value={summary.total} />
        <Stat label="Failures" value={summary.failures} tone="text-red-600" />
        <Stat label="Active users" value={summary.active_users} />
        <Stat label="Activity types" value={summary.by_type.length} />
      </div>
      <div className="card flex flex-wrap gap-2 p-3">
        {summary.by_type.map((t) => (
          <button
            key={t.activity_type}
            type="button"
            onClick={() =>
              setFilters((f) => ({
                ...f,
                offset: 0,
                activity_type: f.activity_type === t.activity_type ? '' : t.activity_type,
              }))
            }
            className={`rounded-full px-3 py-1 text-xs font-medium ring-1 transition ring-inset ${
              filters.activity_type === t.activity_type
                ? 'bg-blue-600 text-white ring-blue-600'
                : 'bg-white text-slate-700 ring-slate-200 hover:bg-slate-50'
            }`}
          >
            {humanize(t.activity_type)} · {t.success + t.failure}
            {t.failure > 0 && <span className="ml-1 text-red-500">({t.failure} failed)</span>}
          </button>
        ))}
      </div>

      <FilterBar
        value={filters}
        onChange={setFilters}
        show={['user', 'activityType', 'status', 'q']}
      />

      <Panel title="Activity feed">
        <DataTable
          columns={[
            'created_at',
            'actor_email',
            'activity_type',
            'action',
            'file_id',
            'status',
            'ip_address',
          ]}
          rows={feed.items}
          empty="No activity matches these filters."
          render={{
            created_at: (value, row) => (
              <span className={row.isNew ? 'font-semibold text-blue-700' : ''}>
                {new Date(value).toLocaleTimeString('en-GB')}{' '}
                <span className="text-xs text-slate-400">
                  {new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                </span>
              </span>
            ),
            actor_email: (value) =>
              value || <span className="text-slate-400">anonymous / system</span>,
            activity_type: (value) => humanize(value),
            status: (value) => <StatusBadge status={value} />,
          }}
        />
        <Pager
          offset={filters.offset}
          limit={LIMIT}
          total={feed.total}
          onChange={(offset) => setFilters((f) => ({ ...f, offset }))}
        />
      </Panel>
    </div>
  );
}

function Stat({ label, value, tone = 'text-slate-950' }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tracking-tight ${tone}`}>
        {value.toLocaleString('en-IN')}
      </p>
    </div>
  );
}
