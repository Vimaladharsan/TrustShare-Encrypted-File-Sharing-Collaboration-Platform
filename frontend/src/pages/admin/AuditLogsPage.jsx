import { Download, ShieldCheck, ShieldX } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { exportAuditLogs, filterAuditLogs, verifyAuditLogs } from '../../api/monitoring';
import { PageHeader, Panel } from '../../components/admin/AdminBits';
import { DataTable, FilterBar, Pager, StatusBadge } from '../../components/admin/MonitoringBits';
import { humanize } from '../../utils/monitoring';
import Button from '../../components/Button';
import { ErrorState, Loading } from '../../components/StateMessage';

const LIMIT = 25;

/** Audit Logs: the permanent, hash-chained history – filters, integrity check and CSV export. */
export default function AuditLogsPage() {
  const [filters, setFilters] = useState({ offset: 0 });
  const [page, setPage] = useState(null);
  const [integrity, setIntegrity] = useState(null);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);

  const load = useCallback(() => {
    setError('');
    filterAuditLogs({ ...filters, limit: LIMIT })
      .then(setPage)
      .catch((err) => setError(getErrorMessage(err)));
  }, [filters]);

  useEffect(load, [load]);
  useEffect(() => {
    verifyAuditLogs()
      .then(setIntegrity)
      .catch(() => setIntegrity({ valid: false, reason: 'could not be checked' }));
  }, []);

  async function exportCsv() {
    setExporting(true);
    try {
      await exportAuditLogs(filters);
      toast.success('Audit log exported (this export is itself recorded)');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Audit logs"
        text="A permanent history of who did what, when and from where. Entries can't be edited or deleted."
      >
        <Button variant="secondary" onClick={exportCsv} loading={exporting}>
          <Download className="size-4" aria-hidden="true" /> Export CSV
        </Button>
      </PageHeader>

      {integrity && <IntegrityBanner integrity={integrity} />}

      <FilterBar
        value={filters}
        onChange={setFilters}
        show={['dates', 'user', 'activityType', 'status', 'fileId', 'q']}
      />

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !page && <Loading />}
      {!error && page && (
        <Panel title={`${page.total.toLocaleString('en-IN')} entries`}>
          <DataTable
            columns={['seq', 'created_at', 'username', 'activity_type', 'description', 'file_id',
              'status', 'ip_address', 'hash']} // prettier-ignore
            rows={page.items}
            empty="No audit entries match these filters."
            render={{
              seq: (value, row) => (
                <span
                  className="font-mono text-xs text-slate-500"
                  title={row.imported ? 'Imported history' : ''}
                >
                  #{value}
                  {row.imported && '*'}
                </span>
              ),
              username: (value) => value || <span className="text-slate-400">anonymous</span>,
              activity_type: (value) => humanize(value),
              status: (value) => <StatusBadge status={value} />,
              file_id: (value) =>
                value ? (
                  <button
                    type="button"
                    onClick={() => setFilters((f) => ({ ...f, file_id: value, offset: 0 }))}
                    className="font-mono text-xs text-blue-700 hover:underline"
                    title="Show everything that happened to this file"
                  >
                    {value.slice(0, 10)}…
                  </button>
                ) : (
                  <span className="text-slate-300">—</span>
                ),
              hash: (value) => (
                <span className="font-mono text-xs text-slate-400" title={value}>
                  {value.slice(0, 8)}
                </span>
              ),
            }}
          />
          <Pager
            offset={filters.offset}
            limit={LIMIT}
            total={page.total}
            onChange={(offset) => setFilters((f) => ({ ...f, offset }))}
          />
        </Panel>
      )}
      <p className="text-xs text-slate-500">
        * imported from the activity history recorded before the audit log existed. File names are
        never stored here – filter by file ID instead.
      </p>
    </div>
  );
}

function IntegrityBanner({ integrity }) {
  const ok = integrity.valid;
  const Icon = ok ? ShieldCheck : ShieldX;
  return (
    <div
      className={`flex items-start gap-3 rounded-xl p-4 ring-1 ${
        ok
          ? 'bg-emerald-50 text-emerald-900 ring-emerald-200'
          : 'bg-red-50 text-red-900 ring-red-200'
      }`}
    >
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="text-sm">
        <p className="font-semibold">{ok ? 'Integrity verified' : 'Integrity check failed'}</p>
        <p>
          {ok
            ? `All ${integrity.checked.toLocaleString('en-IN')} entries re-checked: every hash links correctly to the one before, so nothing was changed or deleted.`
            : `The chain breaks at entry #${integrity.broken_at_seq ?? '?'} – ${integrity.reason}. Investigate immediately.`}
        </p>
      </div>
    </div>
  );
}
