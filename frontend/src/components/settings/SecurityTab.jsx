import { KeyRound, Lock, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import {
  changePassword,
  getMfaStatus,
  regenerateBackupCodes,
  startMfaSetup,
} from '../../api/account';
import { getErrorMessage } from '../../api/client';
import { useAuth } from '../../auth/useAuth';
import { passwordMeetsRules } from '../../utils/passwordRules';
import Button from '../Button';
import FormField from '../FormField';
import Modal from '../Modal';
import PasswordChecklist from '../PasswordChecklist';
import { ErrorState, Loading } from '../StateMessage';
import BackupCodes from './BackupCodes';
import MfaDisableDialog from './MfaDisableDialog';
import MfaSetupDialog from './MfaSetupDialog';
import SettingsCard from './SettingsCard';

/** Security tab: password and two-step verification (incl. new backup codes). */
export default function SecurityTab() {
  return (
    <div className="space-y-6">
      <SettingsCard
        title="Two-step verification"
        description="A code from your phone at every login – a stolen password alone is not enough."
      >
        <MfaSection />
      </SettingsCard>
      <SettingsCard title="Password" description="Changing it signs out every other device.">
        <PasswordSection />
      </SettingsCard>
    </div>
  );
}

function MfaSection() {
  const { refreshUser } = useAuth();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const [dialog, setDialog] = useState(null); // null | setup | disable | regenerate
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
  if (!status) return <Loading rows={1} />;

  const low = status.backup_codes_remaining <= 3;
  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <span
            className={`grid size-11 shrink-0 place-items-center rounded-xl ring-1 ring-inset ${
              status.enabled
                ? 'bg-emerald-50 text-emerald-600 ring-emerald-100'
                : 'bg-amber-50 text-amber-600 ring-amber-100'
            }`}
          >
            {status.enabled ? (
              <ShieldCheck className="size-5" aria-hidden="true" />
            ) : (
              <ShieldAlert className="size-5" aria-hidden="true" />
            )}
          </span>
          <div>
            <p className="font-semibold text-slate-900">
              {status.enabled ? 'On' : 'Off'}
              <span className="ml-2 font-normal text-slate-500">
                {status.enabled
                  ? '– a code from your phone is needed at every login'
                  : '– your account is protected by your password only'}
              </span>
            </p>
            {status.enabled && (
              <p className={`mt-1 text-sm ${low ? 'text-amber-600' : 'text-slate-500'}`}>
                <KeyRound className="mr-1 inline size-3.5" aria-hidden="true" />
                {status.backup_codes_remaining} backup code
                {status.backup_codes_remaining === 1 ? '' : 's'} left
                {low && ' – generate new ones soon'}
              </p>
            )}
          </div>
        </div>
        {status.enabled ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setDialog({ type: 'regenerate' })}>
              <RefreshCw className="size-4" aria-hidden="true" /> New backup codes
            </Button>
            <Button variant="secondary" onClick={() => setDialog({ type: 'disable' })}>
              Turn off
            </Button>
          </div>
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
      {dialog?.type === 'regenerate' && (
        <RegenerateCodesDialog
          onClose={() => {
            setDialog(null);
            load();
          }}
        />
      )}
    </>
  );
}

/** Ask for a current code, then show the new backup codes once. */
function RegenerateCodesDialog({ onClose }) {
  const [code, setCode] = useState('');
  const [codes, setCodes] = useState(null);
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setWorking(true);
    try {
      setCodes(await regenerateBackupCodes(code.trim()));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setWorking(false);
    }
  }

  if (codes) {
    return (
      <Modal title="Your new backup codes" onClose={onClose}>
        <BackupCodes codes={codes} onDone={onClose} intro="Your old backup codes no longer work." />
      </Modal>
    );
  }

  return (
    <Modal title="Generate new backup codes" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-slate-600">
          Enter the 6-digit code from your authenticator app. You get 10 new codes, and{' '}
          <strong>the old ones stop working</strong>.
        </p>
        <FormField
          label="Authenticator code"
          icon={KeyRound}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="123456"
          autoFocus
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={working} disabled={code.trim().length < 6}>
            Generate codes
          </Button>
        </div>
      </form>
    </Modal>
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
