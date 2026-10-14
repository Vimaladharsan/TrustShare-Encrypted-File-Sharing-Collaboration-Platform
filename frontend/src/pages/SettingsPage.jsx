import { ShieldAlert, ShieldCheck } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getMfaStatus, startMfaSetup } from '../api/account';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../auth/useAuth';
import Button from '../components/Button';
import MfaDisableDialog from '../components/settings/MfaDisableDialog';
import MfaSetupDialog from '../components/settings/MfaSetupDialog';
import { ErrorState, Loading } from '../components/StateMessage';
import { formatDate } from '../utils/format';

/** Account settings: profile details and two-step verification. */
export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Settings</h1>

      <Card title="Profile">
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <Item label="Name" value={user.full_name} />
          <Item
            label="Email"
            value={
              <span className="flex flex-wrap items-center gap-2">
                {user.email}
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    user.is_email_verified
                      ? 'bg-green-50 text-green-700'
                      : 'bg-amber-50 text-amber-700'
                  }`}
                >
                  {user.is_email_verified ? 'Verified' : 'Not verified'}
                </span>
              </span>
            }
          />
          <Item
            label="Role"
            value={
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 capitalize">
                {user.role}
              </span>
            }
          />
          <Item label="Member since" value={formatDate(user.created_at)} />
        </dl>
        <div className="mt-4">
          <p className="text-sm font-medium text-slate-500">What your role allows</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {user.permissions.map((permission) => (
              <li
                key={permission}
                className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700"
              >
                {permission}
              </li>
            ))}
          </ul>
        </div>
      </Card>

      <Card title="Two-step verification">
        <MfaSection />
      </Card>
    </div>
  );
}

function MfaSection() {
  const { refreshUser } = useAuth();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const [dialog, setDialog] = useState(null); // null | { type: 'setup', setup } | { type: 'disable' }
  const [starting, setStarting] = useState(false);

  const load = useCallback(() => {
    setError('');
    getMfaStatus()
      .then(setStatus)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  async function handleTurnOn() {
    setStarting(true);
    try {
      setDialog({ type: 'setup', setup: await startMfaSetup() });
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  async function handleChanged(message) {
    load();
    await refreshUser();
    if (message) toast.success(message);
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!status) return <Loading />;

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          {status.enabled ? (
            <ShieldCheck className="size-8 shrink-0 text-green-600" aria-hidden="true" />
          ) : (
            <ShieldAlert className="size-8 shrink-0 text-amber-500" aria-hidden="true" />
          )}
          <div>
            <p className="font-medium text-slate-900">
              {status.enabled ? 'On' : 'Off'}
              <span className="ml-2 font-normal text-slate-500">
                {status.enabled
                  ? '– a code from your phone is needed at every login'
                  : '– your account is protected by your password only'}
              </span>
            </p>
            {status.enabled && (
              <p
                className={`mt-1 text-sm ${status.backup_codes_remaining <= 3 ? 'text-amber-600' : 'text-slate-500'}`}
              >
                {status.backup_codes_remaining} backup code
                {status.backup_codes_remaining === 1 ? '' : 's'} left
                {status.backup_codes_remaining <= 3 &&
                  ' – turn two-step verification off and on again to get new ones'}
              </p>
            )}
          </div>
        </div>
        {status.enabled ? (
          <Button variant="secondary" onClick={() => setDialog({ type: 'disable' })}>
            Turn off
          </Button>
        ) : (
          <Button onClick={handleTurnOn} loading={starting}>
            Turn on
          </Button>
        )}
      </div>

      {dialog?.type === 'setup' && (
        <MfaSetupDialog
          setup={dialog.setup}
          onClose={() => setDialog(null)}
          onEnabled={() => handleChanged()}
        />
      )}
      {dialog?.type === 'disable' && (
        <MfaDisableDialog
          onClose={() => setDialog(null)}
          onDisabled={() => {
            setDialog(null);
            handleChanged('Two-step verification is off.');
          }}
        />
      )}
    </>
  );
}

function Card({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="mb-4 font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

function Item({ label, value }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-medium text-slate-900">{value}</dd>
    </div>
  );
}
