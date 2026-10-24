import { useState } from 'react';

import { enableMfa, startMfaSetup } from '../../api/account';
import { getErrorCode, getErrorMessage } from '../../api/client';
import Button from '../Button';
import FormField from '../FormField';
import Modal from '../Modal';
import BackupCodes from './BackupCodes';

/**
 * Turning on two-step verification, in two steps:
 *  1. scan the QR code with an authenticator app and type the 6-digit code it shows
 *  2. save the one-time backup codes (shown only once – the server keeps only their hashes)
 *
 * The setup is started by the button click (not in useEffect): StrictMode runs effects twice,
 * and two setups would leave the QR code on screen out of step with the secret on the server.
 */
export default function MfaSetupDialog({ setup: initialSetup, onClose, onEnabled }) {
  const [setup, setSetup] = useState(initialSetup);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [backupCodes, setBackupCodes] = useState(null);

  async function restart() {
    setRestarting(true);
    try {
      setSetup(await startMfaSetup());
      setCode('');
      setError('');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRestarting(false);
    }
  }

  async function handleConfirm(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      setBackupCodes(await enableMfa(code));
      onEnabled();
    } catch (err) {
      setError(getErrorMessage(err));
      if (getErrorCode(err) === 'MFA_SETUP_EXPIRED') await restart();
    } finally {
      setSubmitting(false);
    }
  }

  if (backupCodes) {
    return (
      <Modal title="Save your backup codes" onClose={onClose}>
        <BackupCodes codes={backupCodes} onDone={onClose} />
      </Modal>
    );
  }

  return (
    <Modal title="Turn on two-step verification" onClose={onClose}>
      <form onSubmit={handleConfirm} className="space-y-4">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
          <li>Open Google Authenticator (or any authenticator app) on your phone.</li>
          <li>Scan this QR code.</li>
          <li>Enter the 6-digit code the app shows.</li>
        </ol>
        <img
          src={setup.qr_code}
          alt="QR code for your authenticator app"
          className="mx-auto size-48 rounded-lg border border-slate-200 p-2"
        />
        <details className="text-sm text-slate-600">
          <summary className="cursor-pointer text-blue-600">
            Can't scan? Enter a key instead
          </summary>
          <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 font-mono text-xs break-all">
            {setup.secret}
          </p>
        </details>
        <FormField
          label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="123456"
          maxLength={6}
          autoFocus
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <p className="text-xs text-slate-500">
          This QR code is valid for {Math.round(setup.expires_in / 60)} minutes.{' '}
          <button
            type="button"
            onClick={restart}
            disabled={restarting}
            className="text-blue-600 hover:underline disabled:text-slate-400"
          >
            Get a new one
          </button>
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting} disabled={code.length !== 6}>
            Turn on
          </Button>
        </div>
      </form>
    </Modal>
  );
}
