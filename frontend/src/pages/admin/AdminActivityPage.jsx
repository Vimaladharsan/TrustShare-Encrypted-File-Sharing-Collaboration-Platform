import { FileDown, Search } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';

import { toast } from 'sonner';

import { exportAuditLog, getAuditLog, getLogins, getSecurityEvents } from '../../api/adminReports';
import { getErrorMessage } from '../../api/client';
import {
  DateTime,
  LoginStatusBadge,
  PageHeader,
  SeverityBadge,
  Table,
} from '../../components/admin/AdminBits';
import Button from '../../components/Button';
import { ErrorState, Loading } from '../../components/StateMessage';

const PAGE_SIZE = 25;
const TABS = [
  { value: 'audit', label: 'Audit log' },
  { value: 'logins', label: 'Logins' },
  { value: 'events', label: 'Security events' },
];

/** Admin Activity Logs: the full audit trail, every login, and every security event. */
export default function AdminActivityPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'audit';

  return (
    <div className="space-y-5">
      <PageHeader
        title="Activity logs"
        text="Append-only records of every user action, login and security event."
      />
      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setParams({ tab: t.value })}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.value
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'audit' && <AuditTab />}
      {tab === 'logins' && <LoginsTab />}
      {tab === 'events' && <EventsTab />}
    </div>
  );
}

/** Loads one page of a list. `filterKey` identifies the current filters: when it changes, the
 * list goes back to the first page. */
function usePaged(fetchPage, filterKey) {
  const fetchRef = useRef(fetchPage);
  const [paging, setPaging] = useState({ key: filterKey, page: 0 });
  const page = paging.key === filterKey ? paging.page : 0;
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchRef.current = fetchPage; // always call the latest version (it sees the latest filters)
  });

  const load = useCallback(() => {
    setError('');
    fetchRef
      .current({ limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)));
    // filterKey: reload when the filters change
  }, [page, filterKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(load, [load]);
  const setPage = (next) => setPaging({ key: filterKey, page: next });
  return { page, setPage, data, error, load };
}

function Paged({ state, children }) {
  const { page, setPage, data, error, load } = state;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading />;
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  return (
    <div className="space-y-3">
      <div className="card min-w-0 p-2">{children(data)}</div>
      <div className="flex items-center justify-between text-sm text-slate-600">
        <span>{data.total} record(s)</span>
        {pages > 1 && (
          <div className="flex items-center gap-3">
            <span>
              Page {page + 1} of {pages}
            </span>
            <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button
              variant="secondary"
              disabled={page + 1 >= pages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function Chips({ options, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(([v, label]) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${value === v ? 'bg-slate-900 text-white shadow-sm' : 'bg-white text-slate-600 ring-1 ring-slate-200 ring-inset hover:bg-slate-50 hover:text-slate-900'}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function summary(details) {
  return Object.entries(details || {})
    .filter(([, v]) => v !== null && typeof v !== 'object')
    .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}`)
    .join(' · ');
}

function AuditTab() {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [group, setGroup] = useState('');
  const [status, setStatus] = useState('');
  const [exporting, setExporting] = useState(false);

  async function exportCsv() {
    setExporting(true);
    try {
      await exportAuditLog({ q: query, group: group || undefined, status: status || undefined });
      toast.success('Audit log exported (this export is itself recorded)');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const state = usePaged(
    (paging) =>
      getAuditLog({ q: query, group: group || undefined, status: status || undefined, ...paging }),
    `${query}|${group}|${status}`,
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <label className="relative block lg:w-80">
          <span className="sr-only">Search the audit log</span>
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Email, action or IP address"
            className="w-full rounded-lg border border-slate-300 py-2 pr-3 pl-9 text-sm shadow-xs focus:border-blue-500 focus:ring-4 focus:ring-blue-500/15 focus:outline-none"
          />
        </label>
        <div className="flex flex-wrap gap-4">
          <Chips
            value={group}
            onChange={setGroup}
            options={[
              ['', 'All'],
              ['auth', 'Sign-in'],
              ['files', 'Files'],
              ['sharing', 'Sharing'],
              ['admin', 'Admin'],
            ]}
          />
          <Chips
            value={status}
            onChange={setStatus}
            options={[
              ['', 'Any result'],
              ['failure', 'Failures'],
            ]}
          />
          <Button
            variant="secondary"
            loading={exporting}
            onClick={exportCsv}
            title="Download the records matching these filters (max 10,000) as CSV"
          >
            <FileDown className="size-4" aria-hidden="true" /> Export CSV
          </Button>
        </div>
      </div>
      <Paged state={state}>
        {(data) => (
          <Table
            empty="No matching records."
            head={['Action', 'Who', 'Result', 'Details', 'IP address', 'Date & time']}
            rows={data.items.map((e, i) => [
              `${e.created_at}-${i}`,
              <code key="a" className="text-xs">
                {e.action}
              </code>,
              e.actor_email || 'Link visitor / system',
              e.status === 'success' ? 'Success' : <span className="text-red-700">Failure</span>,
              <span key="d" className="block max-w-xs truncate" title={summary(e.details)}>
                {summary(e.details) || '—'}
              </span>,
              <code key="ip" className="text-xs">
                {e.ip_address || '—'}
              </code>,
              <DateTime key="t" value={e.created_at} />,
            ])}
          />
        )}
      </Paged>
    </div>
  );
}

function LoginsTab() {
  const [status, setStatus] = useState('');
  const state = usePaged((paging) => getLogins({ status: status || undefined, ...paging }), status);
  return (
    <div className="space-y-3">
      <Chips
        value={status}
        onChange={setStatus}
        options={[
          ['', 'All'],
          ['success', 'Successful'],
          ['failed', 'Failed'],
        ]}
      />
      <Paged state={state}>
        {(data) => (
          <Table
            empty="No logins."
            head={[
              'User',
              'Email',
              'Status',
              'Method / reason',
              'IP address',
              'Location',
              'Date & time',
            ]}
            rows={data.items.map((l, i) => [
              `${l.created_at}-${i}`,
              l.user_name || <span className="text-slate-400">Unknown user</span>,
              l.email || '—',
              <LoginStatusBadge key="s" status={l.status} />,
              (l.method || l.reason || '—').replaceAll('_', ' '),
              <code key="ip" className="text-xs">
                {l.ip_address || '—'}
              </code>,
              l.location,
              <DateTime key="t" value={l.created_at} />,
            ])}
          />
        )}
      </Paged>
    </div>
  );
}

function EventsTab() {
  const [severity, setSeverity] = useState('');
  const state = usePaged(
    (paging) => getSecurityEvents({ severity: severity || undefined, ...paging }),
    severity,
  );
  return (
    <div className="space-y-3">
      <Chips
        value={severity}
        onChange={setSeverity}
        options={[
          ['', 'All'],
          ['high', 'High'],
          ['medium', 'Medium'],
          ['low', 'Low'],
          ['info', 'Info'],
        ]}
      />
      <Paged state={state}>
        {(data) => (
          <Table
            empty="No security events."
            head={['Event', 'Severity', 'Who', 'Details', 'IP address', 'Date & time']}
            rows={data.items.map((e, i) => [
              `${e.created_at}-${i}`,
              e.message,
              <SeverityBadge key="s" severity={e.severity} />,
              e.actor_email || '—',
              <span key="d" className="block max-w-xs truncate" title={summary(e.details)}>
                {summary(e.details) || '—'}
              </span>,
              <code key="ip" className="text-xs">
                {e.ip_address || '—'}
              </code>,
              <DateTime key="t" value={e.created_at} />,
            ])}
          />
        )}
      </Paged>
    </div>
  );
}
