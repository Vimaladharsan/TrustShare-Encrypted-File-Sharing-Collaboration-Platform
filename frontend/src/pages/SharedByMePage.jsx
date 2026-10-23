import { Link2, Share2, UserRound } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import { listSentShares, revokeShare } from '../api/shares';
import Button from '../components/Button';
import ConfirmDialog from '../components/ConfirmDialog';
import ShareStatusBadge from '../components/shares/ShareStatusBadge';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import { formatDate } from '../utils/format';
import { downloadsLabel, expiryLabel, permissionLabel } from '../utils/shares';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'ended', label: 'Ended' },
];

/** Every link and direct share I created, with its live status, downloads and a Revoke button. */
export default function SharedByMePage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [confirm, setConfirm] = useState(null);

  const load = useCallback(() => {
    setError('');
    listSentShares()
      .then(setItems)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  function askRevoke(share) {
    setConfirm({
      title: 'Revoke this share?',
      message:
        share.share_type === 'link'
          ? `Anyone using this link to “${share.file_name}” will lose access immediately.`
          : `${share.recipient_name} will lose access to “${share.file_name}” immediately.`,
      action: async () => {
        try {
          await revokeShare(share.id);
          toast.success('Share revoked');
          load();
        } catch (err) {
          toast.error(getErrorMessage(err));
        }
      },
    });
  }

  const shown = (items || []).filter((share) => {
    if (filter === 'active') return share.status === 'active';
    if (filter === 'ended') return share.status !== 'active';
    return true;
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Shared by me</h1>
          <p className="text-sm text-slate-500">
            Links and people you shared files with. Create shares from My Files (⋮ → Share).
          </p>
        </div>
        <div className="flex gap-2">
          {FILTERS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={`rounded-full px-3 py-1 text-sm ${
                filter === value
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
      {!error && !items && <Loading />}
      {!error && items && shown.length === 0 && (
        <Empty
          icon={Share2}
          title={items.length ? 'No shares match this filter' : "You haven't shared anything yet"}
          text="Open My Files, click ⋮ next to a file and choose Share."
        />
      )}

      {!error && shown.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">File</th>
                <th className="px-4 py-3 font-medium">Shared with</th>
                <th className="px-4 py-3 font-medium">Access</th>
                <th className="px-4 py-3 font-medium">Expires</th>
                <th className="px-4 py-3 font-medium">Downloads</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((share) => (
                <tr key={share.id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">
                      {share.file_name ?? 'Deleted file'}
                    </p>
                    <p className="text-xs text-slate-500">Created {formatDate(share.created_at)}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-2 text-slate-700">
                      {share.share_type === 'link' ? (
                        <>
                          <Link2 className="size-4 text-slate-400" aria-hidden="true" /> Anyone with
                          the link
                        </>
                      ) : (
                        <>
                          <UserRound className="size-4 text-slate-400" aria-hidden="true" />
                          {share.recipient_email}
                        </>
                      )}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{permissionLabel(share.permission)}</td>
                  <td className="px-4 py-3 text-slate-600">{expiryLabel(share.expires_at)}</td>
                  <td className="px-4 py-3 text-slate-600">{downloadsLabel(share)}</td>
                  <td className="px-4 py-3">
                    <ShareStatusBadge status={share.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {share.status !== 'revoked' && (
                      <Button variant="secondary" onClick={() => askRevoke(share)}>
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel="Revoke"
          onConfirm={confirm.action}
          onClose={() => setConfirm(null)}
        />
      )}
    </div>
  );
}
