import { Copy, History, Link2, Pencil, ShieldCheck, UserRound } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { PREVIEWABLE } from '../../api/files';
import { createShare, createSharesBulk, listFileShares, revokeShare } from '../../api/shares';
import Button from '../Button';
import Modal from '../Modal';
import {
  HOUR,
  LINK_MAX_DAYS,
  customExpiryError,
  downloadsLabel,
  expiryLabel,
  permissionLabel,
  toLocalInput,
} from '../../utils/shares';
import AccessHistoryDialog from './AccessHistoryDialog';
import CreatedLink from './CreatedLink';
import EditShareDialog from './EditShareDialog';
import ShareStatusBadge from './ShareStatusBadge';

const LINK_EXPIRY = [
  { value: HOUR, label: '1 hour' },
  { value: 24 * HOUR, label: '1 day' },
  { value: 7 * 24 * HOUR, label: '7 days' },
  { value: 30 * 24 * HOUR, label: '30 days (maximum)' },
];
const CUSTOM = -1;
const PERSON_EXPIRY = [{ value: 0, label: 'Never' }, ...LINK_EXPIRY.slice(1, 3)];

const inputClass =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 shadow-xs focus:ring-4 focus:ring-blue-500/15 focus:outline-none';

/**
 * Share one file – or several selected files at once (`files`) – as a secret link (anyone who has
 * it; one link per file) or with a registered person ("Shared with me"), with view / download
 * permission, expiry and an optional download limit. New links can be shown as a QR code.
 * For a single file it also lists the file's existing shares (edit / revoke).
 */
export default function ShareDialog({ file, files, onClose }) {
  const items = files ?? [file];
  const multi = items.length > 1;
  const firstId = items[0].id;
  const canView = items.every((item) => PREVIEWABLE.includes(item.extension));
  const [mode, setMode] = useState('link'); // 'link' | 'user'
  const [permission, setPermission] = useState(canView ? 'view' : 'download');
  const [expiry, setExpiry] = useState(7 * 24 * HOUR);
  const [customAt, setCustomAt] = useState('');
  const [limit, setLimit] = useState('');
  const [email, setEmail] = useState('');
  const [working, setWorking] = useState(false);
  const [createdLinks, setCreatedLinks] = useState([]); // [{ id, file_name, url }]
  const [shares, setShares] = useState(null);
  const [editing, setEditing] = useState(null); // the share being edited
  const [historyOf, setHistoryOf] = useState(null); // the share whose access history is open

  const customProblem = expiry === CUSTOM ? customExpiryError(customAt, mode) : '';

  const loadShares = useCallback(() => {
    if (multi) return;
    listFileShares(firstId)
      .then(setShares)
      .catch(() => setShares([]));
  }, [firstId, multi]);

  useEffect(loadShares, [loadShares]);

  function switchMode(next) {
    setMode(next);
    setExpiry(next === 'link' ? 7 * 24 * HOUR : 0);
    setCustomAt('');
    setCreatedLinks([]);
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
      if (multi) {
        const result = await createSharesBulk(
          items.map((item) => item.id),
          body,
        );
        const done = result.created.length;
        if (mode === 'link') setCreatedLinks(result.created);
        else if (done) {
          toast.success(`Shared ${done} files with ${email.trim()} – they get one notice`);
          setEmail('');
        }
        if (result.failed.length) {
          const name = items.find((item) => item.id === result.failed[0].file_id)?.name;
          toast.warning(
            `${done} shared, ${result.failed.length} skipped – ${name}: ${result.failed[0].message}`,
          );
        }
      } else {
        const created = await createShare(firstId, body);
        if (created.url) setCreatedLinks([created]);
        else {
          toast.success(`Shared with ${created.recipient_name} – we emailed them a notice`);
          setEmail('');
        }
        loadShares();
      }
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setWorking(false);
    }
  }

  async function copyAll() {
    const text = createdLinks.map((link) => `${link.file_name}: ${link.url}`).join('\n');
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${createdLinks.length} links copied`);
    } catch {
      toast.error('Copy failed – copy the links one by one.');
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
    <Modal
      title={multi ? `Share ${items.length} files` : `Share “${items[0].name}”`}
      onClose={onClose}
      width="max-w-2xl"
    >
      {multi && (
        <p
          className="mb-4 truncate text-sm text-slate-500"
          title={items.map((i) => i.name).join(', ')}
        >
          {items.map((item) => item.name).join(' · ')}
        </p>
      )}
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
                View only
                {canView ? '' : multi ? ' (not for all selected types)' : ' (not for this type)'}
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
            {mode === 'link'
              ? multi
                ? `Create ${items.length} links`
                : 'Create link'
              : multi
                ? `Share ${items.length} files`
                : 'Share'}
          </Button>
        </div>
      </form>

      {createdLinks.length > 0 && (
        <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3">
          {multi && (
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-blue-900">
                {createdLinks.length} links created – one per file
              </p>
              <Button size="sm" variant="secondary" onClick={copyAll}>
                <Copy className="size-3.5" aria-hidden="true" /> Copy all
              </Button>
            </div>
          )}
          <div className={multi ? 'max-h-72 space-y-3 overflow-y-auto pr-1' : ''}>
            {createdLinks.map((link) => (
              <CreatedLink
                key={link.id}
                url={link.url}
                fileName={link.file_name}
                showName={multi}
              />
            ))}
          </div>
          <p className="mt-3 flex items-start gap-1.5 text-xs text-blue-800">
            <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            Copy {multi ? 'them' : 'it'} now: TrustShare keeps only a fingerprint (hash) of each
            link, so it can&apos;t be shown again. You can always create a new one.
          </p>
        </div>
      )}

      <div className={multi ? 'hidden' : 'mt-6'}>
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
                <Button
                  variant="ghost"
                  onClick={() => setHistoryOf(share)}
                  aria-label="Access history"
                  title="Who opened, viewed or downloaded it"
                >
                  <History className="size-4" aria-hidden="true" />
                </Button>
                {share.status !== 'revoked' && (
                  <>
                    <Button
                      variant="ghost"
                      onClick={() => setEditing(share)}
                      aria-label="Edit share"
                      title="Change permission, expiry or download limit"
                    >
                      <Pencil className="size-4" aria-hidden="true" />
                    </Button>
                    <Button variant="secondary" onClick={() => revoke(share)}>
                      Revoke
                    </Button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {historyOf && <AccessHistoryDialog share={historyOf} onClose={() => setHistoryOf(null)} />}
      {editing && (
        <EditShareDialog share={editing} onSaved={loadShares} onClose={() => setEditing(null)} />
      )}
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
