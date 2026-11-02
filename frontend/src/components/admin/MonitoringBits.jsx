import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { useEffect, useState } from 'react';

import { listUsers } from '../../api/admin';
import { SERIES, OTHER } from '../../utils/charts';
import { formatBytes } from '../../utils/format';
import { ACTIVITY_TYPES, FILE_TYPES, humanize } from '../../utils/monitoring';
import { StackedBars } from '../analytics/AnalyticsCharts';
import { ChartCard, DateRangeFilter } from '../analytics/AnalyticsParts';
import { DateTime } from './AdminBits';

// Shared pieces of the Milestone 3 admin pages (monitoring, audit, reports, analytics, alerts).

const select = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm';

/**
 * The brief's filters in one bar. `show` lists which ones a page needs:
 * dates, user, fileType, activityType, fileId, status, q
 */
export function FilterBar({ value, onChange, show = [], children }) {
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState(value.q || '');
  const set = (patch) => onChange({ ...value, ...patch, offset: 0 });

  useEffect(() => {
    if (!show.includes('user')) return;
    listUsers({ limit: 100 })
      .then((data) => setUsers(data.items))
      .catch(() => setUsers([]));
  }, [show]);

  return (
    <div className="card flex flex-wrap items-center gap-2 p-3">
      {show.includes('dates') && (
        <DateRangeFilter
          range={value}
          onChange={(range) => set({ from: range.from, to: range.to, preset: range.preset })}
        />
      )}
      {show.includes('user') && (
        <select
          value={value.user_id || ''}
          onChange={(e) => set({ user_id: e.target.value })}
          className={select}
          aria-label="User"
        >
          <option value="">All users</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name} ({u.email})
            </option>
          ))}
        </select>
      )}
      {show.includes('activityType') && (
        <select
          value={value.activity_type || ''}
          onChange={(e) => set({ activity_type: e.target.value })}
          className={select}
          aria-label="Activity type"
        >
          <option value="">All activity types</option>
          {ACTIVITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {humanize(t)}
            </option>
          ))}
        </select>
      )}
      {show.includes('fileType') && (
        <select
          value={value.file_type || ''}
          onChange={(e) => set({ file_type: e.target.value })}
          className={select}
          aria-label="File type"
        >
          <option value="">All file types</option>
          {FILE_TYPES.map((t) => (
            <option key={t} value={t}>
              {humanize(t)}s
            </option>
          ))}
        </select>
      )}
      {show.includes('status') && (
        <select
          value={value.status || ''}
          onChange={(e) => set({ status: e.target.value })}
          className={select}
          aria-label="Status"
        >
          <option value="">Success and failure</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
        </select>
      )}
      {show.includes('fileId') && (
        <input
          value={value.file_id || ''}
          onChange={(e) => set({ file_id: e.target.value.trim() })}
          placeholder="File ID"
          maxLength={24}
          className={`${select} w-56 font-mono`}
          aria-label="File ID"
        />
      )}
      {show.includes('q') && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            set({ q: q.trim() });
          }}
          className="relative"
        >
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search name, email, IP…"
            className={`${select} w-60 pl-9`}
            aria-label="Search"
          />
        </form>
      )}
      {children}
    </div>
  );
}

/** Headline numbers from a {key: number} object. Keys with "bytes" are shown as sizes. */
export function StatGrid({ summary }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {Object.entries(summary).map(([key, value]) => (
        <div key={key} className="card p-4">
          <p className="text-xs font-medium text-slate-500">{humanize(key)}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
            {key.includes('bytes') ? formatBytes(value) : value.toLocaleString('en-IN')}
          </p>
        </div>
      ))}
    </div>
  );
}

function cell(key, value) {
  if (value === null || value === undefined || value === '') {
    return <span className="text-slate-300">—</span>;
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (key.includes('bytes')) return formatBytes(value);
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return <DateTime value={value} />;
  }
  if (key.endsWith('_id') && typeof value === 'string' && value.length > 20) {
    return (
      <span className="font-mono text-xs text-slate-500" title={value}>
        {value.slice(0, 10)}…
      </span>
    );
  }
  return String(value);
}

/** A table from plain rows: [{column: value}] – dates, sizes and IDs formatted automatically. */
export function DataTable({ columns, rows, empty = 'Nothing to show.', render = {} }) {
  if (!rows.length) return <p className="py-8 text-center text-sm text-slate-500">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-3 py-2.5 whitespace-nowrap">
                {humanize(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {rows.map((row, i) => (
            <tr key={row.id || row.log_id || row.alert_id || i} className="hover:bg-slate-50/80">
              {columns.map((c) => (
                <td key={c} className="px-3 py-2.5">
                  {render[c] ? render[c](row[c], row) : cell(c, row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Stacked bars per day for rows like {date, a: 1, b: 2}. */
export function DayChart({ title, rows }) {
  const keys = rows.length ? Object.keys(rows[0]).filter((k) => k !== 'date') : [];
  const series = keys.map((key, i) => ({
    key,
    label: humanize(key),
    color: SERIES[i] || OTHER,
  }));
  const legend = series.map((s) => ({ ...s, value: rows.reduce((n, r) => n + r[s.key], 0) }));
  return (
    <ChartCard
      title={title}
      legend={legend}
      empty={legend.every((s) => s.value === 0)}
      emptyText="Nothing in this period."
    >
      <StackedBars days={rows} series={series} />
    </ChartCard>
  );
}

export function Pager({ offset, limit, total, onChange }) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <div className="flex items-center justify-between px-3 py-2 text-sm text-slate-500">
      <span>
        {total.toLocaleString('en-IN')} entries · page {page} of {pages}
      </span>
      <div className="flex gap-1">
        <button
          type="button"
          disabled={page === 1}
          onClick={() => onChange(Math.max(0, offset - limit))}
          className="rounded-lg p-1.5 hover:bg-slate-100 disabled:opacity-40"
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" />
        </button>
        <button
          type="button"
          disabled={page === pages}
          onClick={() => onChange(offset + limit)}
          className="rounded-lg p-1.5 hover:bg-slate-100 disabled:opacity-40"
          aria-label="Next page"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>
    </div>
  );
}

const STATUS = {
  open: 'bg-red-50 text-red-700 ring-red-600/15',
  acknowledged: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  resolved: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-600/15',
  failure: 'bg-red-50 text-red-700 ring-red-600/15',
};

export function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${
        STATUS[status] || 'bg-slate-100 text-slate-600 ring-slate-500/10'
      }`}
    >
      {humanize(status)}
    </span>
  );
}
