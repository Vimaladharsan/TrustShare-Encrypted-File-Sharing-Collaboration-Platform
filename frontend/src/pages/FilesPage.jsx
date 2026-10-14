import {
  Download,
  Eye,
  FolderInput,
  FolderPlus,
  Inbox,
  Pencil,
  SearchX,
  Trash2,
  Upload,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useOutletContext, useParams, useSearchParams } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import {
  createFolder,
  downloadFile,
  getFolder,
  listFiles,
  listFolders,
  trashFile,
  trashFolder,
  updateFile,
  updateFolder,
} from '../api/files';
import { useAuth } from '../auth/useAuth';
import Button from '../components/Button';
import Breadcrumbs from '../components/files/Breadcrumbs';
import FilePreviewDialog from '../components/files/FilePreviewDialog';
import FileTable from '../components/files/FileTable';
import FolderGrid from '../components/files/FolderGrid';
import UploadModal from '../components/files/UploadModal';
import MoveDialog from '../components/MoveDialog';
import NameDialog from '../components/NameDialog';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import { CATEGORIES } from '../utils/format';

/**
 * "My Files" (top level), one folder (/folders/:folderId), or search results (/search?q=).
 */
export default function FilesPage({ mode = 'folder' }) {
  const { folderId } = useParams();
  const [params] = useSearchParams();
  const query = mode === 'search' ? params.get('q') || '' : '';
  const navigate = useNavigate();
  const { can } = useAuth();
  const { refreshUsage } = useOutletContext();

  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState([]);
  const [crumbs, setCrumbs] = useState([]);
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [error, setError] = useState('');
  const [sort, setSort] = useState({ by: 'date', order: 'desc' });
  const [category, setCategory] = useState('');
  const [dialog, setDialog] = useState(null); // { type, item }

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      const fileOptions = { category, sort: sort.by, order: sort.order };
      if (mode === 'search') {
        setFolders([]);
        setCrumbs([]);
        setFiles(await listFiles({ ...fileOptions, folderId: 'all', q: query }));
      } else {
        const [folderList, fileList, detail] = await Promise.all([
          listFolders({ parentId: folderId }),
          listFiles({ ...fileOptions, folderId }),
          folderId ? getFolder(folderId) : Promise.resolve(null),
        ]);
        setFolders(folderList);
        setFiles(fileList);
        setCrumbs(detail ? detail.breadcrumbs : []);
      }
      setStatus('ready');
    } catch (err) {
      setError(getErrorMessage(err));
      setStatus('error');
    }
  }, [mode, folderId, query, category, sort]);

  useEffect(() => {
    load();
  }, [load]);

  // Runs an action, shows a toast, reloads the list. Errors become a red toast.
  async function run(action, successMessage) {
    try {
      await action();
      if (successMessage) toast.success(successMessage);
      load();
      refreshUsage();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  function toggleSort(by) {
    setSort((current) =>
      current.by === by
        ? { by, order: current.order === 'asc' ? 'desc' : 'asc' }
        : { by, order: by === 'name' ? 'asc' : 'desc' },
    );
  }

  const canEditFiles = can('file:update');
  const canUpload = can('file:upload');
  const currentFolderName = crumbs.length ? crumbs[crumbs.length - 1].name : 'My Files';
  const canManageFolders = can('folder:manage');

  const fileActions = (file) => [
    { label: 'Preview', icon: Eye, onClick: () => setDialog({ type: 'preview', item: file }) },
    { label: 'Download', icon: Download, onClick: () => run(() => downloadFile(file)) },
    canEditFiles && {
      label: 'Rename',
      icon: Pencil,
      onClick: () => setDialog({ type: 'renameFile', item: file }),
    },
    canEditFiles && {
      label: 'Move to…',
      icon: FolderInput,
      onClick: () => setDialog({ type: 'moveFile', item: file }),
    },
    canEditFiles && {
      label: 'Move to trash',
      icon: Trash2,
      danger: true,
      onClick: () => run(() => trashFile(file.id), `“${file.name}” moved to trash`),
    },
  ];

  const folderActions = (folder) =>
    canManageFolders
      ? [
          {
            label: 'Rename',
            icon: Pencil,
            onClick: () => setDialog({ type: 'renameFolder', item: folder }),
          },
          {
            label: 'Move to…',
            icon: FolderInput,
            onClick: () => setDialog({ type: 'moveFolder', item: folder }),
          },
          {
            label: 'Move to trash',
            icon: Trash2,
            danger: true,
            onClick: () => run(() => trashFolder(folder.id), `“${folder.name}” moved to trash`),
          },
        ]
      : [];

  const isEmpty = folders.length === 0 && files.length === 0;

  return (
    <div className="mx-auto max-w-6xl">
      {/* ---------- header: where am I + actions ---------- */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {mode === 'search' ? (
          <h1 className="text-lg font-semibold text-slate-900">Search results for “{query}”</h1>
        ) : (
          <Breadcrumbs crumbs={crumbs} />
        )}
        {mode === 'folder' && (
          <div className="flex gap-2">
            {canManageFolders && (
              <Button variant="secondary" onClick={() => setDialog({ type: 'newFolder' })}>
                <FolderPlus className="size-4" aria-hidden="true" />
                New folder
              </Button>
            )}
            {canUpload && (
              <Button onClick={() => setDialog({ type: 'upload' })}>
                <Upload className="size-4" aria-hidden="true" />
                Upload
              </Button>
            )}
          </div>
        )}
      </div>

      {/* ---------- category filter ---------- */}
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filter by type">
        {CATEGORIES.map(({ value, label }) => (
          <button
            key={label}
            type="button"
            onClick={() => setCategory(value)}
            aria-pressed={category === value}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              category === value
                ? 'border-blue-600 bg-blue-50 text-blue-700'
                : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ---------- content ---------- */}
      <div className="mt-6">
        {status === 'loading' && <Loading />}
        {status === 'error' && <ErrorState message={error} onRetry={load} />}
        {status === 'ready' && isEmpty && mode === 'search' && (
          <Empty icon={SearchX} title="No matching files" text="Try a different name or filter." />
        )}
        {status === 'ready' && isEmpty && mode === 'folder' && (
          <Empty
            icon={Inbox}
            title={category ? 'No files of this type here' : 'This folder is empty'}
            text={canUpload ? 'Upload files or create a folder to get started.' : ''}
          >
            {canUpload && !category && (
              <Button onClick={() => setDialog({ type: 'upload' })}>
                <Upload className="size-4" aria-hidden="true" />
                Upload files
              </Button>
            )}
          </Empty>
        )}
        {status === 'ready' && !isEmpty && (
          <div className="space-y-6">
            {folders.length > 0 && (
              <section>
                <h2 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Folders
                </h2>
                <FolderGrid
                  folders={folders}
                  onOpen={(folder) => navigate(`/folders/${folder.id}`)}
                  actionsFor={canManageFolders ? folderActions : null}
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
                  sort={sort}
                  onSort={toggleSort}
                  actionsFor={fileActions}
                  onOpen={(file) => setDialog({ type: 'preview', item: file })}
                />
              </section>
            )}
          </div>
        )}
      </div>

      {/* ---------- dialogs ---------- */}
      {dialog?.type === 'preview' && (
        <FilePreviewDialog
          file={dialog.item}
          onDownload={() => run(() => downloadFile(dialog.item))}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'upload' && (
        <UploadModal
          folderId={folderId}
          folderName={currentFolderName}
          onUploaded={() => {
            load();
            refreshUsage();
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'newFolder' && (
        <NameDialog
          title="New folder"
          label="Folder name"
          submitLabel="Create"
          onClose={() => setDialog(null)}
          onSubmit={async (name) => {
            await createFolder(name, folderId);
            toast.success(`Folder “${name}” created`);
            load();
          }}
        />
      )}
      {dialog?.type === 'renameFolder' && (
        <NameDialog
          title="Rename folder"
          label="Folder name"
          submitLabel="Rename"
          initialValue={dialog.item.name}
          onClose={() => setDialog(null)}
          onSubmit={async (name) => {
            await updateFolder(dialog.item.id, { name });
            load();
          }}
        />
      )}
      {dialog?.type === 'renameFile' && (
        <NameDialog
          title="Rename file"
          label="File name"
          submitLabel="Rename"
          initialValue={dialog.item.name}
          onClose={() => setDialog(null)}
          onSubmit={async (name) => {
            await updateFile(dialog.item.id, { name });
            load();
          }}
        />
      )}
      {dialog?.type === 'moveFile' && (
        <MoveDialog
          itemName={dialog.item.name}
          onClose={() => setDialog(null)}
          onMove={async (destination) => {
            await updateFile(dialog.item.id, { folder_id: destination });
            toast.success('File moved');
            load();
          }}
        />
      )}
      {dialog?.type === 'moveFolder' && (
        <MoveDialog
          itemName={dialog.item.name}
          excludeId={dialog.item.id}
          onClose={() => setDialog(null)}
          onMove={async (destination) => {
            await updateFolder(dialog.item.id, { parent_id: destination });
            toast.success('Folder moved');
            load();
          }}
        />
      )}
    </div>
  );
}
