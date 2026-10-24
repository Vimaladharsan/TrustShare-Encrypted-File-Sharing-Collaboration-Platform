import { Check, Copy, Link2, ShieldCheck, UserRound } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { PREVIEWABLE } from '../../api/files';
import { createShare, listFileShares, revokeShare } from '../../api/shares';
import Button from '../Button';
import Modal from '../Modal';
import { downloadsLabel, expiryLabel, permissionLabel } from '../../utils/shares';
import ShareStatusBadge from './ShareStatusBadge';

const HOUR = 60 * 60 * 1000;
const LINK_EXPIRY = [
  { value: HOUR, label: '1 hour' },
  { value: 24 * HOUR, label: '1 day' },
  { value: 7 * 24 * HOUR, label: '7 days' },
  { value: 30 * 24 * HOUR, label: '30 days (maximum)' },
];
const CUSTOM = -1;
const PERSON_EXPIRY = [{ value: 0, label: 'Never' }, ...LINK_EXPIRY.slice(1, 3)];
const LINK_MAX_DAYS = 30; // the server's SHARE_LINK_MAX_DAYS

/** Value for <input type="datetime-local">: local time, minutes precision. */
function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

/** Problem with a custom expiry, or '' if it is fine. */
function customExpiryError(value, mode) {
  if (!value) return 'Pick a date and time.';
  const when = new Date(value).getTime();
  if (Number.isNaN(when) || when <= Date.now()) return 'Pick a time in the future.';
  if (mode === 'link' && when > Date.now() + LINK_MAX_DAYS * 24 * HOUR) {
    return `Links can last at most ${LINK_MAX_DAYS} days.`;
  }
  return '';
}

const inputClass =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 shadow-xs focus:ring-4 focus:ring-blue-500/15 focus:outline-none';

/**
 * Share one file: a secret link (anyone who has it) or a registered person ("Shared with me"),
 * with view / download permission, expiry and an optional download limit. Also lists the file's
 * existing shares so they can be revoked.
 */
export default function ShareDialog({ file, onClose }) {
  const canView = PREVIEWABLE.includes(file.extension);
  const [mode, setMode] = useState('link'); // 'link' | 'user'
  const [permission, setPermission] = useState(canView ? 'view' : 'download');
  const [expiry, setExpiry] = useState(7 * 24 * HOUR);
  const [customAt, setCustomAt] = useState('');
  const [limit, setLimit] = useState('');
  const [email, setEmail] = useState('');
  const [working, setWorking] = useState(false);
  const [createdUrl, setCreatedUrl] = useState('');
  const [copied, setCopied] = useState(false);
  const [shares, setShares] = useState(null);

  const customProblem = expiry === CUSTOM ? customExpiryError(customAt, mode) : '';

  const loadShares = useCallback(() => {
    listFileShares(file.id)
      .then(setShares)
      .catch(() => setShares([]));
  }, [file.id]);

  useEffect(loadShares, [loadShares]);

  function switchMode(next) {
    setMode(next);
    setExpiry(next === 'link' ? 7 * 24 * HOUR : 0);
    setCustomAt('');
    setCreatedUrl('');
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (expiry === CUSTOM && customProblem) {
      toast.error(customProblem);
      return;
    }
    setWorking(true);
    try {
      const body = { share_type: mode, permission };
      if (expiry === CUSTOM) body.expires_at = new Date(customAt).toISOString();
      else if (expiry) body.expires_at = new Date(Date.now() + expiry).toISOString();
      if (permission === 'download' && limit) body.max_downloads = Number(limit);
      if (mode === 'user') body.recipient_email = email.trim();
      const created = await createShare(file.id, body);
      if (created.url) {
        setCreatedUrl(created.url);
        setCopied(false);
      } else {
        toast.success(`Shared with ${created.recipient_name} – we emailed them a notice`);
        setEmail('');
      }
      loadShares();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setWorking(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(createdUrl);
      setCopied(true);
      toast.success('Link copied');
    } catch {
      toast.error('Copy failed – select the link and copy it manually.');
    }
  }

  async function revoke(share) {
    try {
      await revokeShare(share.id);
      toast.success('Share revoked – it no longer works');
      loadShares();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <Modal title={`Share “${file.name}”`} onClose={onClose} width="max-w-2xl">
      <div className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 text-sm font-medium">
        <ModeButton active={mode === 'link'} onClick={() => switchMode('link')} icon={Link2}>
          Anyone with the link
        </ModeButton>
        <ModeButton active={mode === 'user'} onClick={() => switchMode('user')} icon={UserRound}>
          Specific people
        </ModeButton>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === 'user' && (
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Their TrustShare email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@example.com"
              className={inputClass}
            />
          </label>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
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
            <span className="mb-1 block font-medium text-slate-700">Expires after</span>
            <select
              value={expiry}
              onChange={(e) => setExpiry(Number(e.target.value))}
              className={inputClass}
            >
              {(mode === 'link' ? LINK_EXPIRY : PERSON_EXPIRY).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
              <option value={CUSTOM}>Custom date & time…</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Download limit</span>
            <input
              type="number"
              min="1"
              max="1000"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              disabled={permission !== 'download'}
              placeholder="No limit"
              className={`${inputClass} disabled:bg-slate-50`}
            />
          </label>
        </div>

        {expiry === CUSTOM && (
          <label className="block text-sm sm:max-w-xs">
            <span className="mb-1 block font-medium text-slate-700">Expires on</span>
            <input
              type="datetime-local"
              required
              value={customAt}
              min={toLocalInput(new Date(Date.now() + 5 * 60000))}
              max={
                mode === 'link'
                  ? toLocalInput(new Date(Date.now() + LINK_MAX_DAYS * 24 * HOUR))
                  : undefined
              }
              onChange={(e) => setCustomAt(e.target.value)}
              aria-invalid={Boolean(customAt && customProblem)}
              className={inputClass}
            />
            <span
              className={`mt-1 block text-xs ${customAt && customProblem ? 'text-red-600' : 'text-slate-500'}`}
            >
              {customAt && customProblem
                ? customProblem
                : customAt
                  ? `Stops working ${new Date(customAt).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })} (your time).`
                  : 'Your local time.'}
            </span>
          </label>
        )}

        <div className="flex justify-end">
          <Button
            type="submit"
            loading={working}
            disabled={expiry === CUSTOM && Boolean(customProblem)}
          >
            {mode === 'link' ? 'Create link' : 'Share'}
          </Button>
        </div>
      </form>

      {createdUrl && (
        <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3">
          <div className="flex gap-2">
            <input
              readOnly
              value={createdUrl}
              onFocus={(e) => e.target.select()}
              aria-label="Share link"
              className="min-w-0 flex-1 rounded-lg border border-blue-200 bg-white px-3 py-2 font-mono text-xs"
            />
            <Button onClick={copy}>
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
          <p className="mt-2 flex items-start gap-1.5 text-xs text-blue-800">
            <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            Copy it now: TrustShare keeps only a fingerprint (hash) of this link, so it can&apos;t
            be shown again. You can always create a new one.
          </p>
        </div>
      )}

      <div className="mt-6">
        <h3 className="mb-2 text-sm font-semibold text-slate-900">Current shares</h3>
        {shares === null && <p className="text-sm text-slate-500">Loading…</p>}
        {shares?.length === 0 && (
          <p className="text-sm text-slate-500">This file isn&apos;t shared yet.</p>
        )}
        {shares?.length > 0 && (
          <ul className="max-h-56 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
            {shares.map((share) => (
              <li key={share.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                {share.share_type === 'link' ? (
                  <Link2 className="size-4 shrink-0 text-slate-400" aria-hidden="true" />
                ) : (
                  <UserRound className="size-4 shrink-0 text-slate-400" aria-hidden="true" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-slate-800">
                    {share.share_type === 'link' ? 'Share link' : share.recipient_email}
                  </p>
                  <p className="text-xs text-slate-500">
                    {permissionLabel(share.permission)} · {expiryLabel(share.expires_at)} ·
                    Downloads {downloadsLabel(share)}
                  </p>
                </div>
                <ShareStatusBadge status={share.status} />
                {share.status !== 'revoked' && (
                  <Button variant="secondary" onClick={() => revoke(share)}>
                    Revoke
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}

function ModeButton({ active, onClick, icon: Icon, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 ${
        active ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
      }`}
    >
      <Icon className="size-4" aria-hidden="true" />
      {children}
    </button>
  );
}
