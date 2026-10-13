import { RotateCcw, Trash2, XCircle } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import { deleteFile, listFiles, listFolders, restoreFile, restoreFolder } from '../api/files';
import { useAuth } from '../auth/useAuth';
import ConfirmDialog from '../components/ConfirmDialog';
import FileTable from '../components/files/FileTable';
import FolderGrid from '../components/files/FolderGrid';
import { Empty, ErrorState, Loading } from '../components/StateMessage';

/** Items in the trash: restore them, or delete files forever. Trash still counts toward quota. */
export default function TrashPage() {
  const { can } = useAuth();
  const { refreshUsage } = useOutletContext();
  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [toDelete, setToDelete] = useState(null);

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      const [folderList, fileList] = await Promise.all([
        listFolders({ trashed: true }),
        listFiles({ trashed: true, sort: 'date', order: 'desc' }),
      ]);
      setFolders(folderList);
      setFiles(fileList);
      setStatus('ready');
    } catch (err) {
      setError(getErrorMessage(err));
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(action, message) {
    try {
      await action();
      toast.success(message);
      load();
      refreshUsage();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  const canUpdate = can('file:update');
  const fileActions = (file) => [
    canUpdate && {
      label: 'Restore',
      icon: RotateCcw,
      onClick: () => run(() => restoreFile(file.id), `“${file.name}” restored`),
    },
    can('file:delete') && {
      label: 'Delete forever',
      icon: XCircle,
      danger: true,
      onClick: () => setToDelete(file),
    },
  ];
  const folderActions = (folder) => [
    {
      label: 'Restore',
      icon: RotateCcw,
      onClick: () => run(() => restoreFolder(folder.id), `“${folder.name}” restored`),
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="text-lg font-semibold text-slate-900">Trash</h1>
      <p className="mt-1 text-sm text-slate-500">
        Items here still count toward your storage until they are deleted forever.
      </p>

      <div className="mt-6">
        {status === 'loading' && <Loading />}
        {status === 'error' && <ErrorState message={error} onRetry={load} />}
        {status === 'ready' && folders.length === 0 && files.length === 0 && (
          <Empty icon={Trash2} title="Trash is empty" />
        )}
        {status === 'ready' && (folders.length > 0 || files.length > 0) && (
          <div className="space-y-6">
            {folders.length > 0 && (
              <FolderGrid
                folders={folders}
                onOpen={() => toast.info('Restore the folder to open it.')}
                actionsFor={can('folder:manage') ? folderActions : null}
              />
            )}
            {files.length > 0 && <FileTable files={files} actionsFor={fileActions} />}
          </div>
        )}
      </div>

      {toDelete && (
        <ConfirmDialog
          title="Delete forever?"
          message={`“${toDelete.name}” will be permanently deleted. This cannot be undone.`}
          confirmLabel="Delete forever"
          onClose={() => setToDelete(null)}
          onConfirm={() => run(() => deleteFile(toDelete.id), 'File deleted forever')}
        />
      )}
    </div>
  );
}
