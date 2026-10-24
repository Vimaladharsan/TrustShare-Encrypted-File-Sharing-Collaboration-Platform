import { Download, Eye, Star, StarOff } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getFavorites, unstarFile } from '../api/analytics';
import { getErrorMessage } from '../api/client';
import { downloadFile } from '../api/files';
import FilePreviewDialog from '../components/files/FilePreviewDialog';
import FileTable from '../components/files/FileTable';
import { Empty, ErrorState, Loading } from '../components/StateMessage';

/** Files I starred (⋮ → Add to favorites in My Files), newest star first. */
export default function FavoritesPage() {
  const [files, setFiles] = useState(null);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);

  const load = useCallback(() => {
    setError('');
    getFavorites()
      .then(setFiles)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  async function run(action, message) {
    try {
      await action();
      if (message) toast.success(message);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  const actionsFor = (file) => [
    { label: 'Preview', icon: Eye, onClick: () => setPreview(file) },
    { label: 'Download', icon: Download, onClick: () => run(() => downloadFile(file)) },
    {
      label: 'Remove from favorites',
      icon: StarOff,
      onClick: () => run(() => unstarFile(file.id).then(load), 'Removed from favorites'),
    },
  ];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Favorites</h1>
        <p className="mt-1 text-sm text-slate-500">Files you starred for quick access.</p>
      </div>
      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !files && <Loading />}
      {!error && files?.length === 0 && (
        <Empty
          icon={Star}
          title="No favorites yet"
          text="In My Files, click ⋮ next to a file and choose Add to favorites."
        />
      )}
      {!error && files?.length > 0 && (
        <FileTable files={files} actionsFor={actionsFor} onOpen={setPreview} />
      )}
      {preview && (
        <FilePreviewDialog
          file={preview}
          onDownload={() => run(() => downloadFile(preview))}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
