import { AlertTriangle, KeyRound, Lock, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import { deleteAccount } from '../../api/account';
import { getErrorMessage } from '../../api/client';
import { useAuth } from '../../auth/useAuth';
import Button from '../Button';
import FormField from '../FormField';
import Modal from '../Modal';
import SettingsCard from './SettingsCard';

const CONSEQUENCES = [
  'All your files are deleted forever, together with their encryption keys.',
  'Every share link and direct share you created stops working.',
  'You are signed out on every device and can no longer log in.',
  'Your activity log is kept as an audit record, as required for security.',
];

/** Account tab: delete my account (the "danger zone"). */
export default function DeleteAccountCard() {
  const [open, setOpen] = useState(false);
  return (
    <SettingsCard
      tone="danger"
      title="Delete account"
      description="Permanently delete your TrustShare account and everything in it."
    >
      <ul className="space-y-2 text-sm text-slate-600">
        {CONSEQUENCES.map((line) => (
          <li key={line} className="flex gap-2">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-400" aria-hidden="true" />
            {line}
          </li>
        ))}
      </ul>
      <Button variant="danger" className="mt-5" onClick={() => setOpen(true)}>
        <Trash2 className="size-4" aria-hidden="true" /> Delete my account
      </Button>
      {open && <DeleteAccountDialog onClose={() => setOpen(false)} />}
    </SettingsCard>
  );
}

function DeleteAccountDialog({ onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);

  // Password accounts type DELETE; Google-only accounts (no password) type their email.
  const phrase = user.has_password ? 'DELETE' : user.email;
  const ready =
    confirm.trim().toLowerCase() === phrase.toLowerCase() &&
    (!user.has_password || password) &&
    (!user.mfa_enabled || code.trim().length >= 6);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setWorking(true);
    try {
      await deleteAccount({
        password: user.has_password ? password : null,
        code: user.mfa_enabled ? code.trim() : null,
        confirm: confirm.trim(),
      });
      // Leave the protected page first, otherwise clearing the user redirects to /login.
      navigate('/', { replace: true });
      toast.success('Your account and all your files were deleted.');
      await logout().catch(() => {}); // the server already ended every session
    } catch (err) {
      setError(getErrorMessage(err));
      setWorking(false);
    }
  }

  return (
    <Modal title="Delete your account?" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-3 rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-100 ring-inset">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            This <strong>cannot be undone</strong>. Your files and their encryption keys are
            destroyed, so not even a backup can bring them back.
          </p>
        </div>
        {user.has_password && (
          <FormField
            label="Your password"
            icon={Lock}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        )}
        {user.mfa_enabled && (
          <FormField
            label="Two-step code"
            icon={KeyRound}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="Code from your app or a backup code"
            required
          />
        )}
        <FormField
          label={
            <>
              Type <span className="font-mono font-semibold text-red-600">{phrase}</span> to confirm
            </>
          }
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="off"
          spellCheck={false}
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
          <Button type="submit" variant="danger" loading={working} disabled={!ready}>
            <Trash2 className="size-4" aria-hidden="true" /> Delete forever
          </Button>
        </div>
      </form>
    </Modal>
  );
}
