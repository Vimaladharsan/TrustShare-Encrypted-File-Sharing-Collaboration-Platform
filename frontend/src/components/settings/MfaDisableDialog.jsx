import { useState } from 'react';

import { disableMfa } from '../../api/account';
import { getErrorMessage } from '../../api/client';
import Button from '../Button';
import FormField from '../FormField';
import Modal from '../Modal';

/** Turning MFA off needs both factors again, so a stolen session alone can't remove it. */
export default function MfaDisableDialog({ onClose, onDisabled }) {
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await disableMfa(password, code.trim());
      onDisabled();
    } catch (err) {
      setError(getErrorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <Modal title="Turn off two-step verification" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-slate-600">
          Your account will be protected by your password only. Confirm with your password and a
          code from your authenticator app (or a backup code).
        </p>
        <FormField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          autoFocus
          required
        />
        <FormField
          label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          autoComplete="one-time-code"
          placeholder="123456"
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
          <Button
            type="submit"
            variant="danger"
            loading={submitting}
            disabled={!password || code.trim().length < 6}
          >
            Turn off
          </Button>
        </div>
      </form>
    </Modal>
  );
}
