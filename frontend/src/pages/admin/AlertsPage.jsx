import { CheckCircle2, Eye, RotateCcw, ScrollText } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { getAlerts, getDetectionRules, updateAlert } from '../../api/monitoring';
import { DateTime, PageHeader, Panel, SeverityBadge } from '../../components/admin/AdminBits';
import { DataTable, FilterBar, Pager, StatusBadge } from '../../components/admin/MonitoringBits';
import { humanize } from '../../utils/monitoring';
import Button from '../../components/Button';
import Modal from '../../components/Modal';
import { ErrorState, Loading } from '../../components/StateMessage';
import { useNotifications } from '../../notifications/useNotifications';

const LIMIT = 20;
const select = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm';
const TYPES = [
  'repeated_failed_logins',
  'repeated_unauthorized_access',
  'excessive_downloads',
  'expired_link_abuse',
  'revoked_link_abuse',
  'multiple_failed_logins',
  'account_locked',
  'suspicious_ip',
  'new_ip_login',
  'token_reuse',
  'unauthorized_access',
  'blocked_request',
  'policy_violation',
  'file_threat',
  'download_anomaly',
  'vault_locked',
  'admin_action',
];

/** Suspicious Activity Alerts: the alert inbox with the workflow open → acknowledged → resolved. */
export default function AlertsPage() {
  const { version } = useNotifications();
  const [filters, setFilters] = useState({ offset: 0, status: 'open' });
  const [page, setPage] = useState(null);
  const [rules, setRules] = useState([]);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => {
    setError('');
    const { status, q, ...rest } = filters;
    getAlerts({ ...rest, user: q, status: status === 'all' ? '' : status, limit: LIMIT })
      .then(setPage)
      .catch((err) => setError(getErrorMessage(err)));
  }, [filters]);

  useEffect(load, [load, version]); // a new live alert refreshes the list
  useEffect(() => {
    getDetectionRules()
      .then(setRules)
      .catch(() => setRules([]));
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Suspicious activity alerts"
        text="Raised automatically by the detection rules and security checks. Acknowledge while you look into one, resolve it with a note."
      />

      <FilterBar value={filters} onChange={setFilters} show={['dates', 'q']}>
        <select
          value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value, offset: 0 }))}
          className={select}
          aria-label="Status"
        >
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
          <option value="all">All statuses</option>
        </select>
        <select
          value={filters.severity || ''}
          onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value, offset: 0 }))}
          className={select}
          aria-label="Severity"
        >
          <option value="">All severities</option>
          {['high', 'medium', 'low', 'info'].map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </select>
        <select
          value={filters.type || ''}
          onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value, offset: 0 }))}
          className={select}
          aria-label="Event type"
        >
          <option value="">All event types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {humanize(t)}
            </option>
          ))}
        </select>
      </FilterBar>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !page && <Loading />}
      {!error && page && (
        <Panel title={`${page.total.toLocaleString('en-IN')} alerts`}>
          <DataTable
            columns={[
              'created_at',
              'severity',
              'title',
              'actor_email',
              'ip_address',
              'status',
              'id',
            ]}
            rows={page.items}
            empty="No alerts match these filters – all quiet."
            render={{
              severity: (value) => <SeverityBadge severity={value} />,
              title: (value, row) => (
                <span>
                  <span className="font-medium text-slate-900">{value}</span>
                  {row.rule && (
                    <span className="block text-xs text-slate-500">
                      {row.rule.count} in {row.rule.window_minutes} min (limit {row.rule.limit})
                    </span>
                  )}
                </span>
              ),
              actor_email: (value) => value || <span className="text-slate-400">—</span>,
              status: (value) => <StatusBadge status={value} />,
              id: (_, row) => (
                <Button variant="secondary" size="sm" onClick={() => setSelected(row)}>
                  Review
                </Button>
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

      <Panel title="Detection rules (thresholds from the server settings)">
        <DataTable
          columns={['title', 'severity', 'condition', 'per', 'counts']}
          rows={rules}
          render={{ severity: (value) => <SeverityBadge severity={value} /> }}
        />
      </Panel>

      {selected && (
        <AlertDialog
          alert={selected}
          onClose={() => setSelected(null)}
          onChanged={() => {
            setSelected(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function AlertDialog({ alert, onClose, onChanged }) {
  const [note, setNote] = useState(alert.note || '');
  const [working, setWorking] = useState('');
  const navigate = useNavigate();

  /** Audit logs of this user (or, for anonymous visitors, this IP) 30 min before/after the alert. */
  function investigate() {
    const params = new URLSearchParams({ around: alert.created_at });
    if (alert.user_id) params.set('user_id', alert.user_id);
    else if (alert.ip_address) params.set('q', alert.ip_address);
    params.set('who', alert.actor_email || alert.ip_address || 'this alert');
    navigate(`/admin/audit?${params}`);
  }

  async function act(action) {
    setWorking(action);
    try {
      await updateAlert(alert.id, action, note.trim() || null);
      toast.success(`Alert ${action === 'reopen' ? 'reopened' : `${action}d`}`);
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err));
      setWorking('');
    }
  }

  const facts = [
    ['When', <DateTime key="w" value={alert.created_at} />],
    ['Severity', <SeverityBadge key="s" severity={alert.severity} />],
    ['Status', <StatusBadge key="t" status={alert.status} />],
    ['Account', alert.actor_email || '—'],
    ['IP address', alert.ip_address || '—'],
    [
      'Alert ID',
      <span key="i" className="font-mono text-xs">
        {alert.alert_id || alert.id}
      </span>,
    ],
  ];
  if (alert.rule) {
    facts.push([
      'Rule',
      `${humanize(alert.rule.name)}: ${alert.rule.count} in ${alert.rule.window_minutes} min (limit ${alert.rule.limit})`,
    ]);
  }
  if (alert.acknowledged_by) facts.push(['Acknowledged by', alert.acknowledged_by]);
  if (alert.resolved_by) facts.push(['Resolved by', alert.resolved_by]);

  return (
    <Modal title={alert.title} onClose={onClose} width="max-w-xl">
      <p className="text-sm text-slate-600">{alert.message}</p>
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        {facts.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-slate-900">{value}</dd>
          </div>
        ))}
      </dl>
      <label className="mt-4 block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Note (what you found / did)</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          rows={3}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          placeholder="e.g. User forgot their password; confirmed by phone."
        />
      </label>
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        {(alert.user_id || alert.ip_address) && (
          <Button variant="ghost" onClick={investigate} className="mr-auto">
            <ScrollText className="size-4" aria-hidden="true" /> Activity around this time
          </Button>
        )}
        {alert.status !== 'open' && (
          <Button variant="secondary" onClick={() => act('reopen')} loading={working === 'reopen'}>
            <RotateCcw className="size-4" aria-hidden="true" /> Reopen
          </Button>
        )}
        {alert.status === 'open' && (
          <Button
            variant="secondary"
            onClick={() => act('acknowledge')}
            loading={working === 'acknowledge'}
          >
            <Eye className="size-4" aria-hidden="true" /> Acknowledge
          </Button>
        )}
        {alert.status !== 'resolved' && (
          <Button onClick={() => act('resolve')} loading={working === 'resolve'}>
            <CheckCircle2 className="size-4" aria-hidden="true" /> Resolve
          </Button>
        )}
      </div>
    </Modal>
  );
}
