import { useEffect, useState } from 'react';
import { Link } from 'react-router';

import { getMonitoringSummary } from '../../api/monitoring';
import { SeverityBadge } from './AdminBits';

/** The brief's Security Monitoring numbers + the newest open alerts (on the Security dashboard). */
export default function MonitoringSummary({ range }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    getMonitoringSummary(range)
      .then(setData)
      .catch(() => setData(null));
  }, [range]);

  if (!data) return null;
  const cards = [
    ['Security events', data.total_events],
    ['Open alerts', data.open_alerts],
    ['Failed logins', data.failed_logins],
    ['Unauthorized attempts', data.unauthorized_attempts],
    ['Suspicious downloads', data.suspicious_downloads],
    ['Expired link attempts', data.expired_link_attempts],
    ['Revoked link attempts', data.revoked_link_attempts],
  ];
  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-slate-950">Security monitoring</h2>
        <Link to="/admin/alerts" className="text-sm font-medium text-blue-700 hover:underline">
          Review alerts →
        </Link>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-100">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-0.5 text-xl font-semibold text-slate-950">{value}</p>
          </div>
        ))}
      </div>
      {data.recent_alerts.length > 0 && (
        <ul className="mt-4 divide-y divide-slate-100 text-sm">
          {data.recent_alerts.slice(0, 5).map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-2 py-2">
              <SeverityBadge severity={a.severity} />
              <span className="font-medium text-slate-900">{a.title}</span>
              <span className="text-slate-500">{a.actor_email || a.ip_address || ''}</span>
              <span className="ml-auto text-xs text-slate-400">
                {new Date(a.created_at).toLocaleString('en-GB')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
