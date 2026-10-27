import { KeyRound, Lock } from 'lucide-react';
import { useState } from 'react';

import { getErrorMessage } from '../../api/client';
import Button from '../Button';
import FormField from '../FormField';
import Modal from '../Modal';

/**
 * Asks for the vault password before ONE vault action (the password is asked every time and
 * never kept). `onConfirm(password, name)` may throw – the error is shown here.
 * Optional `nameField` ({ label, initialValue }) adds a name input (used for rename).
 */
export default function VaultPasswordDialog({
  title,
  description,
  confirmLabel = 'Continue',
  danger = false,
  nameField,
  onConfirm,
  onClose,
}) {
  const [password, setPassword] = useState('');
  const [name, setName] = useState(nameField?.initialValue ?? '');
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setWorking(true);
    try {
      await onConfirm(password, name.trim());
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
      setPassword('');
      setWorking(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {description && <p className="text-sm text-slate-600">{description}</p>}
        {nameField && (
          <FormField
            label={nameField.label}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        )}
        <FormField
          label="Vault password"
          icon={KeyRound}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="off"
          autoFocus={!nameField}
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-xs text-slate-500">
            <Lock className="size-3.5" aria-hidden="true" /> Asked for every vault action
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant={danger ? 'danger' : 'primary'}
              loading={working}
              disabled={!password || (nameField && !name.trim())}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
