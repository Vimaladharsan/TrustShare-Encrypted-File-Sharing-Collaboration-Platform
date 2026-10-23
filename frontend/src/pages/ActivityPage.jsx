import { CheckCircle2, History, XCircle } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { getMyActivity } from '../api/analytics';
import { getErrorMessage } from '../api/client';
import Button from '../components/Button';
import { Empty, ErrorState, Loading } from '../components/StateMessage';

const PAGE_SIZE = 25;
const GROUPS = [
  { value: '', label: 'All' },
  { value: 'auth', label: 'Sign-in & account' },
  { value: 'files', label: 'Files & folders' },
  { value: 'sharing', label: 'Sharing' },
];

// Human-readable names for the audit actions (anything unknown is shown as-is).
const ACTIONS = {
  'auth.login.success': 'Signed in',
  'auth.login.failed': 'Failed sign-in',
  'auth.login.locked': 'Account locked (too many attempts)',
  'auth.oauth_login': 'Signed in with Google',
  'auth.logout_all': 'Signed out everywhere',
  'auth.password_changed': 'Changed password',
  'auth.password_reset': 'Reset password',
  'auth.password_reset_requested': 'Requested password reset',
  'auth.verify_email': 'Verified email',
  'file.upload': 'Uploaded a file',
  'file.upload_rejected': 'Upload rejected',
  'file.download': 'Downloaded a file',
  'file.preview': 'Opened a file',
  'file.rename': 'Renamed a file',
  'file.move': 'Moved a file',
  'file.trash': 'Moved a file to trash',
  'file.restore': 'Restored a file',
  'file.delete': 'Deleted a file forever',
  'folder.create': 'Created a folder',
  'folder.rename': 'Renamed a folder',
  'folder.move': 'Moved a folder',
  'folder.trash': 'Moved a folder to trash',
  'folder.restore': 'Restored a folder',
  'folder.delete': 'Deleted a folder forever',
  'share.create': 'Shared a file',
  'share.revoke': 'Revoked a share',
  'share.access_denied': 'Share access denied',
};

/** A short, readable summary of an entry's details (file name, reason, method …). */
function describe(entry) {
  const d = entry.details || {};
  const parts = [];
  if (d.file_name) parts.push(d.file_name);
  if (d.name) parts.push(d.name);
  if (d.from && d.to) parts.push(`${d.from} → ${d.to}`);
  if (d.method) parts.push(`via ${d.method}`);
  if (d.share_type)
    parts.push(d.share_type === 'link' ? 'share link' : `with ${d.recipient_email}`);
  if (d.via && d.via !== 'owner')
    parts.push(d.via === 'link' ? 'via share link' : 'shared with you');
  if (d.reason) parts.push(String(d.reason).replaceAll('_', ' ').toLowerCase());
  return parts.join(' · ');
}

/** My own audit trail: every sign-in, file action and share, with IP address and time. */
export default function ActivityPage() {
  const [group, setGroup] = useState('');
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setError('');
    getMyActivity({ group: group || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)));
  }, [group, page]);

  useEffect(load, [load]);

  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));
  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Activity logs</h1>
          <p className="text-sm text-slate-500">
            Everything done with your account. Records can&apos;t be edited or deleted.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {GROUPS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setGroup(value);
                setPage(0);
              }}
              className={`rounded-full px-3 py-1 text-sm ${
                group === value
                  ? 'bg-blue-600 text-white'
                  : 'border border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <Loading />}
      {!error && data?.items.length === 0 && (
        <Empty icon={History} title="No activity yet" text="Your actions will be listed here." />
      )}
      {!error && data?.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">Activity</th>
                <th className="px-4 py-3 font-medium">Details</th>
                <th className="px-4 py-3 font-medium">IP address</th>
                <th className="px-4 py-3 font-medium">Date & time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((entry, index) => (
                <tr key={`${entry.created_at}-${index}`}>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-2 font-medium text-slate-800">
                      {entry.status === 'success' ? (
                        <CheckCircle2 className="size-4 text-green-600" aria-label="Success" />
                      ) : (
                        <XCircle className="size-4 text-red-600" aria-label="Failed" />
                      )}
                      {ACTIONS[entry.action] || entry.action}
                    </span>
                  </td>
                  <td
                    className="max-w-xs truncate px-4 py-3 text-slate-600"
                    title={describe(entry)}
                  >
                    {describe(entry) || '—'}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {entry.ip_address || '—'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-500">
                    {new Date(entry.created_at).toLocaleString('en-GB', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && pages > 1 && (
        <div className="flex items-center justify-end gap-3 text-sm text-slate-600">
          <span>
            Page {page + 1} of {pages}
          </span>
          <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <Button
            variant="secondary"
            disabled={page + 1 >= pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
