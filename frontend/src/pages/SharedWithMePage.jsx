import { Download, Eye, Inbox } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import { downloadReceived, listReceivedShares, previewReceived } from '../api/shares';
import Button from '../components/Button';
import FilePreviewDialog from '../components/files/FilePreviewDialog';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import { fileIcon, formatBytes, formatDate } from '../utils/format';
import { expiryLabel, permissionLabel } from '../utils/shares';

/** Files other TrustShare users shared with me directly (only shares that still work). */
export default function SharedWithMePage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);

  const load = useCallback(() => {
    setError('');
    listReceivedShares()
      .then(setItems)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  async function download(share) {
    try {
      await downloadReceived(share);
    } catch (err) {
      toast.error(getErrorMessage(err));
      load(); // it may have been revoked or expired meanwhile
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Shared with me</h1>
        <p className="text-sm text-slate-500">
          Files other people shared with you. They stay encrypted and you can only do what the owner
          allowed.
        </p>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !items && <Loading />}
      {!error && items?.length === 0 && (
        <Empty
          icon={Inbox}
          title="Nothing shared with you yet"
          text="When someone shares a file with your email, it appears here."
        />
      )}

      {!error && items?.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">File</th>
                <th className="px-4 py-3 font-medium">Shared by</th>
                <th className="px-4 py-3 font-medium">Access</th>
                <th className="px-4 py-3 font-medium">Expires</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((share) => {
                const { Icon, color } = fileIcon(share.category);
                return (
                  <tr key={share.id}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Icon className={`size-5 shrink-0 ${color}`} aria-hidden="true" />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-slate-900">{share.file_name}</p>
                          <p className="text-xs text-slate-500">
                            {formatBytes(share.size_bytes)} · shared {formatDate(share.shared_at)}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-slate-800">{share.owner_name}</p>
                      <p className="text-xs text-slate-500">{share.owner_email}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {permissionLabel(share.permission)}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{expiryLabel(share.expires_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        {share.can_preview && (
                          <Button variant="secondary" onClick={() => setPreview(share)}>
                            <Eye className="size-4" aria-hidden="true" /> Preview
                          </Button>
                        )}
                        {share.permission === 'download' && (
                          <Button variant="secondary" onClick={() => download(share)}>
                            <Download className="size-4" aria-hidden="true" /> Download
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {preview && (
        <FilePreviewDialog
          file={{
            id: preview.id,
            name: preview.file_name,
            extension: preview.extension,
            size_bytes: preview.size_bytes,
          }}
          load={(signal) => previewReceived(preview.id, signal)}
          onDownload={preview.permission === 'download' ? () => download(preview) : undefined}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
