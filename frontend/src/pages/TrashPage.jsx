import { RotateCcw, Trash2, XCircle } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import {
  deleteFile,
  deleteFolder,
  deleteSelected,
  emptyTrash,
  listFiles,
  listFolders,
  restoreAll,
  restoreFile,
  restoreFolder,
  restoreSelected,
} from '../api/files';
import { useAuth } from '../auth/useAuth';
import Button from '../components/Button';
import ConfirmDialog from '../components/ConfirmDialog';
import FileTable from '../components/files/FileTable';
import FolderGrid from '../components/files/FolderGrid';
import { Empty, ErrorState, Loading } from '../components/StateMessage';

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

/**
 * Items in the trash: restore or delete forever – one at a time (⋮), the ticked ones,
 * or everything at once. Trash still counts toward the storage quota.
 */
export default function TrashPage() {
  const { can } = useAuth();
  const { refreshUsage } = useOutletContext();
  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [selectedFolders, setSelectedFolders] = useState(new Set());
  const [confirm, setConfirm] = useState(null); // { title, message, label, action }

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      const [folderList, fileList] = await Promise.all([
        listFolders({ trashed: true }),
        listFiles({ trashed: true, sort: 'date', order: 'desc' }),
      ]);
      setFolders(folderList);
      setFiles(fileList);
      setSelectedFiles(new Set());
      setSelectedFolders(new Set());
      setStatus('ready');
    } catch (err) {
      setError(getErrorMessage(err));
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (setter) => (id) =>
    setter((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  /** Run an action; show a toast summarising the result; reload. */
  async function run(action, successMessage) {
    try {
      const result = await action();
      if (result?.failed?.length) {
        toast.warning(
          `${result.succeeded} done, ${result.failed.length} couldn't be processed: ${result.failed[0].message}`,
        );
      } else {
        toast.success(
          typeof successMessage === 'function' ? successMessage(result) : successMessage,
        );
      }
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
    load();
    refreshUsage();
  }

  const canRestoreFiles = can('file:update');
  const canDelete = can('file:delete');
  const canManageFolders = can('folder:manage');
  const total = files.length + folders.length;
  const selectedCount = selectedFiles.size + selectedFolders.size;

  // ---------- one item (⋮ menu) ----------
  const fileActions = (file) => [
    canRestoreFiles && {
      label: 'Restore',
      icon: RotateCcw,
      onClick: () => run(() => restoreFile(file.id), `“${file.name}” restored`),
    },
    canDelete && {
      label: 'Delete forever',
      icon: XCircle,
      danger: true,
      onClick: () =>
        setConfirm({
          title: 'Delete forever?',
          message: `“${file.name}” will be permanently deleted. This cannot be undone.`,
          label: 'Delete forever',
          action: () => run(() => deleteFile(file.id), 'File deleted forever'),
        }),
    },
  ];
  const folderActions = (folder) => [
    {
      label: 'Restore',
      icon: RotateCcw,
      onClick: () => run(() => restoreFolder(folder.id), `“${folder.name}” restored`),
    },
    canDelete && {
      label: 'Delete forever',
      icon: XCircle,
      danger: true,
      onClick: () =>
        setConfirm({
          title: 'Delete folder forever?',
          message: `“${folder.name}” and everything inside it will be permanently deleted. This cannot be undone.`,
          label: 'Delete forever',
          action: () => run(() => deleteFolder(folder.id), 'Folder deleted forever'),
        }),
    },
  ];

  // ---------- several items ----------
  const fileIds = [...selectedFiles];
  const folderIds = [...selectedFolders];

  function restoreTicked() {
    run(
      () => restoreSelected(fileIds, folderIds),
      (r) => `${plural(r.succeeded, 'item')} restored`,
    );
  }

  function deleteTicked() {
    setConfirm({
      title: `Delete ${plural(selectedCount, 'item')} forever?`,
      message:
        'The selected items (and everything inside selected folders) will be permanently deleted. This cannot be undone.',
      label: 'Delete forever',
      action: () =>
        run(
          () => deleteSelected(fileIds, folderIds),
          (r) => `${plural(r.succeeded, 'item')} deleted forever`,
        ),
    });
  }

  function emptyAll() {
    setConfirm({
      title: 'Empty trash?',
      message: `All ${plural(total, 'item')} in the trash (and everything inside trashed folders) will be permanently deleted. This cannot be undone.`,
      label: 'Empty trash',
      action: () => run(emptyTrash, 'Trash emptied'),
    });
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Trash</h1>
          <p className="mt-1 text-sm text-slate-500">
            Items here still count toward your storage until they are deleted forever.
          </p>
        </div>

        {/* ---------- toolbar: acts on the ticked items, or on everything ---------- */}
        {status === 'ready' && total > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {selectedCount > 0 ? (
              <>
                <span className="text-sm text-slate-600">{selectedCount} selected</span>
                {canRestoreFiles && (
                  <Button variant="secondary" onClick={restoreTicked}>
                    <RotateCcw className="size-4" aria-hidden="true" /> Restore
                  </Button>
                )}
                {canDelete && (
                  <Button variant="danger" onClick={deleteTicked}>
                    <XCircle className="size-4" aria-hidden="true" /> Delete forever
                  </Button>
                )}
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSelectedFiles(new Set());
                    setSelectedFolders(new Set());
                  }}
                >
                  Clear
                </Button>
              </>
            ) : (
              <>
                {canRestoreFiles && (
                  <Button
                    variant="secondary"
                    onClick={() =>
                      run(restoreAll, (r) => `${plural(r.succeeded, 'item')} restored`)
                    }
                  >
                    <RotateCcw className="size-4" aria-hidden="true" /> Restore all
                  </Button>
                )}
                {canDelete && (
                  <Button variant="danger" onClick={emptyAll}>
                    <Trash2 className="size-4" aria-hidden="true" /> Empty trash
                  </Button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      <div className="mt-6">
        {status === 'loading' && <Loading />}
        {status === 'error' && <ErrorState message={error} onRetry={load} />}
        {status === 'ready' && total === 0 && <Empty icon={Trash2} title="Trash is empty" />}
        {status === 'ready' && total > 0 && (
          <div className="space-y-6">
            {folders.length > 0 && (
              <section>
                <h2 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Folders
                </h2>
                <FolderGrid
                  folders={folders}
                  onOpen={(folder) => toggle(setSelectedFolders)(folder.id)}
                  actionsFor={canManageFolders ? folderActions : null}
                  selected={canManageFolders ? selectedFolders : null}
                  onToggle={toggle(setSelectedFolders)}
                />
              </section>
            )}
            {files.length > 0 && (
              <section>
                <h2 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Files
                </h2>
                <FileTable
                  files={files}
                  actionsFor={fileActions}
                  selected={selectedFiles}
                  onToggle={toggle(setSelectedFiles)}
                />
              </section>
            )}
          </div>
        )}
      </div>

      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.label}
          onClose={() => setConfirm(null)}
          onConfirm={confirm.action}
        />
      )}
    </div>
  );
}
