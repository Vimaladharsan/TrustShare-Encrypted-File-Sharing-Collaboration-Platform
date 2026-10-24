import { Lock, LogOut, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import { changePassword, getMfaStatus, startMfaSetup } from '../api/account';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../auth/useAuth';
import Button from '../components/Button';
import ConfirmDialog from '../components/ConfirmDialog';
import FormField from '../components/FormField';
import PasswordChecklist from '../components/PasswordChecklist';
import MfaDisableDialog from '../components/settings/MfaDisableDialog';
import MfaSetupDialog from '../components/settings/MfaSetupDialog';
import { ErrorState, Loading } from '../components/StateMessage';
import { formatDate } from '../utils/format';
import { passwordMeetsRules } from '../utils/passwordRules';

/** Account settings: profile, password, two-step verification and sessions. */
export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Settings</h1>

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

      <Card title="Password">
        <PasswordSection />
      </Card>

      <Card title="Two-step verification">
        <MfaSection />
      </Card>

      <Card title="Sessions">
        <SessionsSection />
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

function PasswordSection() {
  const { user } = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  if (!user.has_password) {
    return (
      <p className="text-sm text-slate-600">
        You sign in with Google, so your account has no password. To add one, use{' '}
        <strong>Forgot password</strong> on the login page.
      </p>
    );
  }

  const matches = next === confirm;
  const canSubmit = current && passwordMeetsRules(next) && matches;

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSaving(true);
    try {
      await changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      toast.success('Password changed. Your other devices have been logged out.');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-md space-y-4">
      <FormField
        label="Current password"
        icon={Lock}
        type="password"
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        autoComplete="current-password"
        required
      />
      <div>
        <FormField
          label="New password"
          icon={Lock}
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
          required
        />
        {next && <PasswordChecklist password={next} />}
      </div>
      <FormField
        label="Confirm new password"
        icon={Lock}
        type="password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        autoComplete="new-password"
        hint={confirm && !matches ? 'Passwords do not match' : undefined}
        required
      />
      {error && (
        <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <Button type="submit" loading={saving} disabled={!canSubmit}>
        Change password
      </Button>
    </form>
  );
}

function SessionsSection() {
  const { logoutAll } = useAuth();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);

  async function handleLogoutAll() {
    await logoutAll();
    toast.success('You have been logged out on every device.');
    navigate('/login');
  }

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-slate-600">
        Lost a device, or logged in on a shared computer? End every session of your account –
        including this one.
      </p>
      <Button variant="secondary" onClick={() => setConfirming(true)} className="shrink-0">
        <LogOut className="size-4" aria-hidden="true" /> Log out of all devices
      </Button>
      {confirming && (
        <ConfirmDialog
          title="Log out of all devices?"
          message="Every device signed in to your account – this one too – will need to log in again."
          confirmLabel="Log out everywhere"
          onConfirm={handleLogoutAll}
          onClose={() => setConfirming(false)}
        />
      )}
    </div>
  );
}

function Card({ title, children }) {
  return (
    <section className="card p-5">
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
