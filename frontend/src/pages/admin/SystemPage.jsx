import { CheckCircle2, KeyRound, RefreshCw, XCircle } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { getHealth, getSystemOverview } from '../../api/adminReports';
import { getErrorMessage } from '../../api/client';
import { PageHeader, Panel } from '../../components/admin/AdminBits';
import Button from '../../components/Button';
import { ErrorState, Loading } from '../../components/StateMessage';
import { presetRange } from '../../utils/charts';

const SERVICES = {
  postgres: ['PostgreSQL', 'Users, roles, wrapped file keys, shares'],
  mongodb: ['MongoDB', 'File metadata, activity logs, security events'],
  redis: ['Redis', 'Sessions, rate limits, one-time tokens'],
  storage: ['Object storage', 'Encrypted file objects (RustFS / AWS S3)'],
};

/** System Monitoring: live health of every service and the state of the encryption keys. */
export default function SystemPage() {
  const [health, setHealth] = useState(null);
  const [keys, setKeys] = useState(null);
  const [error, setError] = useState('');
  const [checkedAt, setCheckedAt] = useState(null);

  const load = useCallback(() => {
    setError('');
    // /health answers 503 when something is down – that is still useful information.
    const healthCall = getHealth().catch((err) => err.response?.data ?? Promise.reject(err));
    Promise.all([healthCall, getSystemOverview(presetRange(7))])
      .then(([h, overview]) => {
        setHealth(h);
        setKeys(overview.keys);
        setCheckedAt(new Date());
      })
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!health || !keys) return <Loading />;
  return (
    <div className="space-y-5">
      <PageHeader
        title="System monitoring"
        text={`Checked ${checkedAt.toLocaleTimeString('en-GB')}.`}
      >
        <Button variant="secondary" onClick={load}>
          <RefreshCw className="size-4" aria-hidden="true" /> Check again
        </Button>
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(SERVICES).map(([key, [name, role]]) => {
          const ok = health.services?.[key] === 'ok';
          return (
            <div
              key={key}
              className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4"
            >
              {ok ? (
                <CheckCircle2 className="size-6 shrink-0 text-green-600" aria-hidden="true" />
              ) : (
                <XCircle className="size-6 shrink-0 text-red-600" aria-hidden="true" />
              )}
              <div>
                <p className="font-medium text-slate-900">
                  {name}{' '}
                  <span className="text-sm font-normal text-slate-500">– {ok ? 'Up' : 'Down'}</span>
                </p>
                <p className="text-sm text-slate-500">{role}</p>
              </div>
            </div>
          );
        })}
      </div>

      <Panel title="Encryption keys">
        <p className="flex items-center gap-2 text-sm text-slate-700">
          <KeyRound className="size-4 text-blue-600" aria-hidden="true" />
          Configured master keys: {keys.configured_versions.map((v) => `v${v}`).join(', ')} · active
          v{keys.active_version}
        </p>
        <ul className="mt-3 space-y-1 text-sm">
          {Object.entries(keys.keys_by_version).map(([version, count]) => (
            <li key={version} className="flex justify-between">
              <span className="text-slate-600">File keys wrapped with v{version}</span>
              <span className="font-medium text-slate-900">{count}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-500">
          Rotate with <code>python -m app.scripts.rotate_keys</code> – see docs/key-management.md.
        </p>
      </Panel>
    </div>
  );
}
