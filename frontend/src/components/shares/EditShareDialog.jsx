import { Info } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { PREVIEWABLE } from '../../api/files';
import { updateShare } from '../../api/shares';
import {
  HOUR,
  LINK_MAX_DAYS,
  customExpiryError,
  expiryLabel,
  toLocalInput,
} from '../../utils/shares';
import Button from '../Button';
import Modal from '../Modal';

const KEEP = 'keep';
const CUSTOM = 'custom';
const NEVER = 'never';
const EXTEND = [
  { value: 24 * HOUR, label: '1 day from now' },
  { value: 7 * 24 * HOUR, label: '7 days from now' },
  { value: 30 * 24 * HOUR, label: '30 days from now' },
];

const inputClass =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 shadow-xs focus:ring-4 focus:ring-blue-500/15 focus:outline-none';

/**
 * Change one share without revoking it: permission, expiry (extend / custom / never for people)
 * and download limit. The link (or the recipient's access) stays the same; an expired or used-up
 * share works again once extended. Only changed values are sent to the server.
 */
export default function EditShareDialog({ share, onSaved, onClose }) {
  const isLink = share.share_type === 'link';
  const extension = (share.file_name || '').split('.').pop().toLowerCase();
  const canView = PREVIEWABLE.includes(extension);
  const [permission, setPermission] = useState(share.permission);
  const [expiry, setExpiry] = useState(KEEP);
  const [customAt, setCustomAt] = useState('');
  const [limit, setLimit] = useState(share.max_downloads ? String(share.max_downloads) : '');
  const [working, setWorking] = useState(false);
  const [passwordMode, setPasswordMode] = useState('keep'); // keep | set | remove (links only)
  const [newPassword, setNewPassword] = useState('');

  const customProblem = expiry === CUSTOM ? customExpiryError(customAt, share.share_type) : '';
  const limitNumber = limit ? Number(limit) : null;
  const limitProblem =
    permission === 'download' && limitNumber !== null && limitNumber < share.download_count
      ? `Already downloaded ${share.download_count} times – the limit can't be lower.`
      : '';
  const ended = share.status === 'expired' || share.status === 'used_up';
  const extendOptions = isLink ? EXTEND : [{ value: NEVER, label: 'Never expires' }, ...EXTEND];

  /** Only what differs from the share as it is now. */
  function changes() {
    const result = {};
    if (permission !== share.permission) result.permission = permission;
    if (expiry === NEVER) result.expires_at = null;
    else if (expiry === CUSTOM) result.expires_at = new Date(customAt).toISOString();
    else if (expiry !== KEEP) result.expires_at = new Date(Date.now() + expiry).toISOString();
    const newLimit = permission === 'download' ? limitNumber : null;
    if (newLimit !== share.max_downloads && permission === 'download') {
      result.max_downloads = newLimit;
    }
    if (passwordMode === 'set') result.password = newPassword;
    if (passwordMode === 'remove') result.password = null;
    return result;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const body = changes();
    if (Object.keys(body).length === 0) {
      onClose();
      return;
    }
    setWorking(true);
    try {
      const updated = await updateShare(share.id, body);
      toast.success(
        ended && updated.status === 'active' ? 'Share is active again' : 'Share updated',
      );
      onSaved();
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
      setWorking(false);
    }
  }

  const who = isLink ? 'the link' : share.recipient_email;

  return (
    <Modal title="Edit share" onClose={onClose} width="max-w-lg">
      <p className="mb-4 text-sm text-slate-500">
        “{share.file_name}” · {isLink ? 'Anyone with the link' : share.recipient_email}. Changes
        apply to {who} immediately – {isLink ? 'the link itself stays the same' : 'no new share'}.
      </p>

      {ended && (
        <p className="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {share.status === 'expired'
            ? 'This share has expired. Pick a new expiry to turn it back on.'
            : 'This share reached its download limit. Raise or remove the limit to turn it back on.'}
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Permission</span>
            <select
              value={permission}
              onChange={(e) => setPermission(e.target.value)}
              className={inputClass}
            >
              <option value="view" disabled={!canView}>
                View only{canView ? '' : ' (not for this type)'}
              </option>
              <option value="download">View & download</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Download limit</span>
            <input
              type="number"
              min={Math.max(1, share.download_count)}
              max="1000"
              value={permission === 'download' ? limit : ''}
              onChange={(e) => setLimit(e.target.value)}
              disabled={permission !== 'download'}
              placeholder={permission === 'download' ? 'No limit' : 'Needs download permission'}
              aria-invalid={Boolean(limitProblem)}
              className={`${inputClass} disabled:bg-slate-50`}
            />
            <span
              className={`mt-1 block text-xs ${limitProblem ? 'text-red-600' : 'text-slate-500'}`}
            >
              {limitProblem || `Downloaded ${share.download_count} times so far.`}
            </span>
          </label>
        </div>

        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Expiry</span>
          <select
            value={expiry}
            onChange={(e) => {
              const value = e.target.value;
              setExpiry(Number.isNaN(Number(value)) ? value : Number(value));
            }}
            className={inputClass}
          >
            <option value={KEEP}>
              Keep: {share.expires_at ? expiryLabel(share.expires_at) : 'never expires'}
              {share.status === 'expired' ? ' (expired)' : ''}
            </option>
            {extendOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
            <option value={CUSTOM}>Custom date & time…</option>
          </select>
        </label>

        {expiry === CUSTOM && (
          <label className="block text-sm sm:max-w-xs">
            <span className="mb-1 block font-medium text-slate-700">Expires on</span>
            <input
              type="datetime-local"
              required
              value={customAt}
              min={toLocalInput(new Date(Date.now() + 5 * 60000))}
              max={
                isLink ? toLocalInput(new Date(Date.now() + LINK_MAX_DAYS * 24 * HOUR)) : undefined
              }
              onChange={(e) => setCustomAt(e.target.value)}
              aria-invalid={Boolean(customAt && customProblem)}
              className={inputClass}
            />
            <span
              className={`mt-1 block text-xs ${customAt && customProblem ? 'text-red-600' : 'text-slate-500'}`}
            >
              {(customAt && customProblem) || 'Your local time.'}
            </span>
          </label>
        )}

        {isLink && (
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Password</span>
            <select
              value={passwordMode}
              onChange={(e) => setPasswordMode(e.target.value)}
              className={inputClass}
            >
              <option value="keep">
                {share.has_password ? 'Keep the current password' : 'No password'}
              </option>
              <option value="set">
                {share.has_password ? 'Set a new password' : 'Add a password'}
              </option>
              {share.has_password && <option value="remove">Remove the password</option>}
            </select>
            {passwordMode === 'set' && (
              <input
                type="password"
                required
                minLength={4}
                maxLength={72}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 4 characters"
                aria-label="New link password"
                autoComplete="new-password"
                className={`${inputClass} mt-2`}
              />
            )}
          </label>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            loading={working}
            disabled={Boolean(customProblem) || Boolean(limitProblem)}
          >
            Save changes
          </Button>
        </div>
      </form>
    </Modal>
  );
}
