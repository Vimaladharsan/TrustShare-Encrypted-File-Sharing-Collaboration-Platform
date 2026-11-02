import { Download } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import { toast } from 'sonner';

import { listUsers } from '../../api/admin';
import { getErrorMessage } from '../../api/client';
import { exportReport, getReport } from '../../api/monitoring';
import { PageHeader, Panel } from '../../components/admin/AdminBits';
import { DataTable, DayChart, FilterBar, StatGrid } from '../../components/admin/MonitoringBits';
import { humanize } from '../../utils/monitoring';
import Button from '../../components/Button';
import { Empty, ErrorState, Loading } from '../../components/StateMessage';
import { presetRange } from '../../utils/charts';

const TABS = [
  { value: 'uploads', label: 'Uploads', filters: ['dates', 'user', 'fileType', 'fileId'] },
  { value: 'downloads', label: 'Downloads', filters: ['dates', 'user', 'fileType', 'fileId'] },
  { value: 'sharing', label: 'Sharing', filters: ['dates', 'user', 'fileType', 'fileId'] },
  { value: 'user', label: 'User activity', filters: ['dates', 'activityType', 'fileId'] },
  { value: 'security', label: 'Security', filters: ['dates', 'user'] },
];

/** File Activity Reports: one page, five reports (tabs), same filters, charts, tables and CSV. */
export default function ReportsPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.value === params.get('tab')) || TABS[0];
  const [filters, setFilters] = useState(() => presetRange(30));
  const [account, setAccount] = useState('');
  const [users, setUsers] = useState([]);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const name = tab.value === 'user' ? (account ? `users/${account}` : null) : tab.value;

  useEffect(() => {
    listUsers({ limit: 100 })
      .then((data) => setUsers(data.items))
      .catch(() => setUsers([]));
  }, []);

  const load = useCallback(() => {
    setError('');
    setReport(null);
    if (!name) return;
    getReport(name, filters)
      .then(setReport)
      .catch((err) => setError(getErrorMessage(err)));
  }, [name, filters]);

  useEffect(load, [load]);

  async function exportCsv() {
    setExporting(true);
    try {
      await exportReport(name, filters);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="File activity reports"
        text="Uploads, downloads, sharing, one user's history and security – from the real records. Files appear by ID and type, never by name."
      >
        {report && (
          <Button variant="secondary" onClick={exportCsv} loading={exporting}>
            <Download className="size-4" aria-hidden="true" /> Export CSV
          </Button>
        )}
      </PageHeader>

      <nav className="flex [scrollbar-width:none] gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setParams({ tab: t.value })}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap ${
              t.value === tab.value
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <FilterBar value={filters} onChange={setFilters} show={tab.filters}>
        {tab.value === 'user' && (
          <select
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            aria-label="User for the report"
          >
            <option value="">Choose a user…</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </select>
        )}
      </FilterBar>

      {!name && (
        <Empty title="Choose a user" text="Pick an account to see its full activity history." />
      )}
      {error && <ErrorState message={error} onRetry={load} />}
      {name && !error && !report && <Loading />}
      {report && <ReportView report={report} />}
    </div>
  );
}

/** Renders any report: summary cards, a chart per day, breakdown tables, then the main table. */
function ReportView({ report }) {
  const { by_day: byDay, ...breakdowns } = report.breakdowns;
  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-slate-950">{report.title}</h2>
      <StatGrid summary={report.summary} />
      {byDay && <DayChart title="Per day" rows={byDay} />}
      <div className="grid gap-5 lg:grid-cols-2">
        {Object.entries(breakdowns).map(([key, rows]) => (
          <Panel key={key} title={humanize(key)}>
            <DataTable
              columns={rows.length ? Object.keys(rows[0]).filter((c) => c !== 'user_id') : []}
              rows={rows}
              empty="Nothing in this period."
            />
          </Panel>
        ))}
      </div>
      <Panel
        title={`Details (${report.rows.length}${report.rows.length >= report.row_limit ? '+' : ''})`}
      >
        <DataTable columns={report.columns} rows={report.rows} empty="Nothing in this period." />
      </Panel>
    </div>
  );
}
