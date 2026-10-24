import { CheckCircle2, LogIn, ShieldAlert, ShieldBan, XCircle } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';

import { getSecurityOverview } from '../../api/adminReports';
import { getErrorMessage } from '../../api/client';
import {
  DateTime,
  LoginStatusBadge,
  PageHeader,
  Panel,
  SeverityBadge,
  Table,
} from '../../components/admin/AdminBits';
import {
  AccessAttemptsChart,
  EventsByTypeChart,
  LoginActivityChart,
} from '../../components/admin/SecurityCharts';
import { DateRangeFilter, SummaryCard } from '../../components/analytics/AnalyticsParts';
import { ErrorState, Loading } from '../../components/StateMessage';
import { presetRange } from '../../utils/charts';

const percent = (part, whole) => (whole ? `${((part / whole) * 100).toFixed(1)}%` : '0%');

/** Admin Security Dashboard: logins, access attempts, security events and recent activity. */
export default function SecurityDashboardPage() {
  const [range, setRange] = useState(() => presetRange(30));
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setError('');
    getSecurityOverview(range)
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)));
  }, [range]);

  useEffect(load, [load]);

  const m = data?.metrics;
  return (
    <div className="space-y-5">
      <PageHeader
        title="Security Dashboard"
        text="Monitor login activity, access attempts, security events and audit logs."
      >
        <DateRangeFilter range={range} onChange={setRange} />
      </PageHeader>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <Loading />}
      {!error && data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <SummaryCard
              icon={LogIn}
              tone="bg-blue-50 text-blue-600"
              label="Total logins"
              value={m.total_logins.value}
              sub="attempts"
              metric={m.total_logins}
            />
            <SummaryCard
              icon={CheckCircle2}
              tone="bg-green-50 text-green-600"
              label="Successful logins"
              value={m.successful_logins.value}
              sub={`${percent(m.successful_logins.value, m.total_logins.value)} success rate`}
              metric={m.successful_logins}
            />
            <SummaryCard
              icon={XCircle}
              tone="bg-red-50 text-red-600"
              label="Failed logins"
              upIsBad
              value={m.failed_logins.value}
              sub={`${percent(m.failed_logins.value, m.total_logins.value)} failure rate`}
              metric={m.failed_logins}
            />
            <SummaryCard
              icon={ShieldBan}
              tone="bg-amber-50 text-amber-700"
              label="Unauthorized attempts"
              upIsBad
              value={m.unauthorized_attempts.value}
              sub="blocked automatically"
              metric={m.unauthorized_attempts}
            />
            <SummaryCard
              icon={ShieldAlert}
              tone="bg-violet-50 text-violet-600"
              label="Security events"
              upIsBad
              value={m.security_events.value}
              sub="all severities"
              metric={m.security_events}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <LoginActivityChart days={data.logins_by_day} />
            <AccessAttemptsChart days={data.access_by_day} />
            <EventsByTypeChart types={data.events_by_type} />
          </div>

          <div className="grid gap-4 2xl:grid-cols-2">
            <Panel title="Recent login activity" action={<ViewAll tab="logins" />}>
              <Table
                empty="No logins yet."
                head={['User', 'Email', 'IP address', 'Status', 'Location', 'Date & time']}
                rows={data.recent_logins.map((l, i) => [
                  i,
                  l.user_name || <span className="text-slate-400">Unknown user</span>,
                  l.email || '—',
                  <code key="ip" className="text-xs">
                    {l.ip_address || '—'}
                  </code>,
                  <LoginStatusBadge key="s" status={l.status} />,
                  l.location,
                  <DateTime key="d" value={l.created_at} />,
                ])}
              />
            </Panel>
            <Panel title="Recent security events" action={<ViewAll tab="events" />}>
              <Table
                empty="No security events yet."
                head={['Event', 'Severity', 'IP address', 'Who', 'Date & time']}
                rows={data.recent_events.map((e, i) => [
                  i,
                  e.message,
                  <SeverityBadge key="s" severity={e.severity} />,
                  <code key="ip" className="text-xs">
                    {e.ip_address || '—'}
                  </code>,
                  e.actor_email || '—',
                  <DateTime key="d" value={e.created_at} />,
                ])}
              />
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

function ViewAll({ tab }) {
  return (
    <Link
      to={`/admin/activity?tab=${tab}`}
      className="text-sm font-medium text-blue-600 hover:underline"
    >
      View all
    </Link>
  );
}
