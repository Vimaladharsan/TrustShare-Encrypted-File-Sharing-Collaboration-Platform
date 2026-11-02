import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';

import { getErrorMessage } from '../../api/client';
import { getNotificationStats } from '../../api/monitoring';
import { listNotifications } from '../../api/notifications';
import { PageHeader, Panel } from '../../components/admin/AdminBits';
import { DataTable, StatusBadge } from '../../components/admin/MonitoringBits';
import { humanize } from '../../utils/monitoring';
import NotificationItem from '../../components/notifications/NotificationItem';
import { ErrorState, Loading } from '../../components/StateMessage';
import { TYPE_LABELS } from '../../notifications/types';
import { useNotifications } from '../../notifications/useNotifications';

const EMAIL_STATUS = {
  sent: 'success',
  failed: 'failure',
  pending: 'acknowledged',
  skipped: 'skipped',
  none: 'in_app_only',
  not_configured: 'not_configured',
};

/** Notification Management: what the system sent, whether emails arrived, and my alert inbox. */
export default function NotificationManagementPage() {
  const { version, markOne } = useNotifications();
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setError('');
    try {
      const [s, inbox] = await Promise.all([
        getNotificationStats(),
        listNotifications({ type: 'security_alert', limit: 10 }),
      ]);
      setStats(s);
      setAlerts(inbox.items);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, version]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!stats) return <Loading />;
  const readRate = stats.total ? Math.round(((stats.total - stats.unread) / stats.total) * 100) : 0;
  return (
    <div className="space-y-5">
      <PageHeader
        title="Notification management"
        text="In-app, live and email notifications sent by TrustShare. Message texts stay private – only the type, recipient and delivery status are shown."
      />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ['Notifications sent', stats.total],
          ['Read', `${readRate}%`],
          ['Emails delivered', stats.emails_sent],
          ['Emails failed', stats.emails_failed],
        ].map(([label, value]) => (
          <div key={label} className="card p-4">
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="My security alert inbox">
          {alerts.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No security alerts.</p>
          ) : (
            alerts.map((item) => (
              <NotificationItem
                key={item.id}
                item={item}
                compact
                onOpen={async (n) => {
                  if (!n.read) await markOne(n.id);
                  navigate('/admin/alerts');
                }}
              />
            ))
          )}
        </Panel>
        <Panel title="By type">
          <DataTable
            columns={['type', 'sent', 'read', 'emails_sent', 'emails_failed']}
            rows={stats.by_type}
            empty="Nothing sent yet."
            render={{ type: (value) => TYPE_LABELS[value] || humanize(value) }}
          />
        </Panel>
      </div>

      <Panel title="Recent deliveries">
        <DataTable
          columns={['created_at', 'type', 'severity', 'recipient_email', 'read', 'email_status']}
          rows={stats.recent}
          empty="Nothing sent yet."
          render={{
            type: (value) => TYPE_LABELS[value] || humanize(value),
            severity: (value) => humanize(value),
            email_status: (value) => <StatusBadge status={EMAIL_STATUS[value] || value} />,
          }}
        />
      </Panel>
    </div>
  );
}
