import { Clock, Download, Eye } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getRecentFiles } from '../api/analytics';
import { getErrorMessage } from '../api/client';
import { downloadFile } from '../api/files';
import FilePreviewDialog from '../components/files/FilePreviewDialog';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import { formatBytes } from '../utils/format';
import FileIcon from '../components/files/FileIcon';

const ACTION_LABEL = {
  'file.upload': 'You uploaded',
  'file.preview': 'You opened',
  'file.download': 'You downloaded',
  'file.rename': 'You renamed',
  'file.move': 'You moved',
};

/** Files I worked with lately – from my own activity, newest first. */
export default function RecentPage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);

  const load = useCallback(() => {
    setError('');
    getRecentFiles()
      .then(setItems)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  async function download(file) {
    try {
      await downloadFile(file);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Recent</h1>
        <p className="mt-1 text-sm text-slate-500">
          Files you recently uploaded, opened, downloaded, renamed or moved.
        </p>
      </div>
      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !items && <Loading />}
      {!error && items?.length === 0 && (
        <Empty icon={Clock} title="Nothing recent" text="Files you work with will show up here." />
      )}
      {!error && items?.length > 0 && (
        <ul className="card divide-y divide-slate-100">
          {items.map(({ file, last_action: action, last_activity_at: at }) => {
            return (
              <li key={file.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                <FileIcon category={file.category} size="sm" />
                <div className="min-w-0 flex-1">
                  <button
                    type="button"
                    onClick={() => setPreview(file)}
                    className="block max-w-full truncate text-left font-medium text-slate-800 hover:text-blue-600 hover:underline"
                  >
                    {file.name}
                  </button>
                  <p className="text-xs text-slate-500">
                    {ACTION_LABEL[action] || 'Activity'} ·{' '}
                    {new Date(at).toLocaleString('en-GB', {
                      day: 'numeric',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}{' '}
                    · {formatBytes(file.size_bytes)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setPreview(file)}
                  className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
                  aria-label={`Preview ${file.name}`}
                >
                  <Eye className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={() => download(file)}
                  className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
                  aria-label={`Download ${file.name}`}
                >
                  <Download className="size-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {preview && (
        <FilePreviewDialog
          file={preview}
          onDownload={() => download(preview)}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
