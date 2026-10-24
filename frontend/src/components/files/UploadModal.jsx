import { CheckCircle2, Copy, UploadCloud, X, XCircle } from 'lucide-react';
import { useRef, useState } from 'react';

import { getErrorCode, getErrorMessage } from '../../api/client';
import { uploadFile } from '../../api/files';
import { formatBytes } from '../../utils/format';
import { ALLOWED_TEXT, MAX_UPLOAD_MB, precheck } from '../../utils/uploadRules';
import Button from '../Button';
import Modal from '../Modal';
import FileIcon from './FileIcon';

const CATEGORY_BY_EXTENSION = {
  pdf: 'document',
  docx: 'document',
  xlsx: 'spreadsheet',
  csv: 'spreadsheet',
  pptx: 'presentation',
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  txt: 'text',
};

let nextId = 0;

/**
 * Drag-and-drop upload dialog. Each file gets its own row:
 * waiting → uploading (progress bar) → done ✓, or error ✕ with the reason.
 * onUploaded() is called after each successful upload so the file list refreshes.
 */
export default function UploadModal({ folderId, folderName, onUploaded, onClose }) {
  const [items, setItems] = useState([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const controllers = useRef({}); // id → AbortController, to cancel an upload

  const update = (id, changes) =>
    setItems((list) => list.map((item) => (item.id === id ? { ...item, ...changes } : item)));

  async function upload(item, allowDuplicate = false) {
    const controller = new AbortController();
    controllers.current[item.id] = controller;
    update(item.id, { status: 'uploading', progress: 0, error: '', code: '' });
    try {
      await uploadFile(item.file, {
        folderId,
        allowDuplicate,
        signal: controller.signal,
        onProgress: (progress) => update(item.id, { progress }),
      });
      update(item.id, { status: 'done', progress: 100 });
      onUploaded();
    } catch (err) {
      if (controller.signal.aborted) {
        update(item.id, { status: 'error', error: 'Upload cancelled.', code: 'CANCELLED' });
      } else {
        update(item.id, { status: 'error', error: getErrorMessage(err), code: getErrorCode(err) });
      }
    } finally {
      delete controllers.current[item.id];
    }
  }

  async function addFiles(fileList) {
    const added = Array.from(fileList).map((file) => {
      const problem = precheck(file);
      return {
        id: (nextId += 1),
        file,
        status: problem ? 'error' : 'waiting',
        progress: 0,
        error: problem || '',
        code: problem ? 'PRECHECK' : '',
      };
    });
    setItems((list) => [...list, ...added]);
    // One at a time keeps the progress bars easy to follow and the server load low.
    for (const item of added.filter((i) => i.status === 'waiting')) {
      await upload(item);
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files);
  }

  const busy = items.some((item) => item.status === 'uploading' || item.status === 'waiting');
  const doneCount = items.filter((item) => item.status === 'done').length;

  return (
    <Modal title={`Upload to “${folderName}”`} onClose={onClose} width="max-w-lg">
      {/* ---------- drop zone ---------- */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        className={`flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-blue-400'
        }`}
      >
        <UploadCloud className="size-10 text-blue-500" aria-hidden="true" />
        <p className="mt-2 text-sm font-medium text-slate-800">
          Drag files here or <span className="text-blue-600">browse</span>
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {ALLOWED_TEXT} · max {MAX_UPLOAD_MB} MB each
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files.length) addFiles(e.target.files);
            e.target.value = ''; // allow choosing the same file again
          }}
        />
      </div>

      {/* ---------- one row per file ---------- */}
      {items.length > 0 && (
        <ul className="mt-4 max-h-72 space-y-2 overflow-y-auto">
          {items.map((item) => (
            <UploadRow
              key={item.id}
              item={item}
              onCancel={() => controllers.current[item.id]?.abort()}
              onKeepBoth={() => upload(item, true)}
              onRetry={() => upload(item)}
            />
          ))}
        </ul>
      )}

      <div className="mt-5 flex items-center justify-between">
        <p className="text-xs text-slate-500">
          {items.length > 0 && `${doneCount} of ${items.length} uploaded`}
        </p>
        <Button onClick={onClose} disabled={busy}>
          {busy ? 'Uploading…' : 'Done'}
        </Button>
      </div>
    </Modal>
  );
}

function UploadRow({ item, onCancel, onKeepBoth, onRetry }) {
  const extension = item.file.name.split('.').pop().toLowerCase();

  return (
    <li className="rounded-lg border border-slate-200 px-3 py-2">
      <div className="flex items-center gap-3">
        <FileIcon category={CATEGORY_BY_EXTENSION[extension]} size="sm" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-800" title={item.file.name}>
            {item.file.name}
          </p>
          <p className="text-xs text-slate-500">
            {formatBytes(item.file.size)}
            {item.status === 'uploading' && ` · ${item.progress}%`}
            {item.status === 'waiting' && ' · waiting…'}
          </p>
        </div>
        {item.status === 'uploading' && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label={`Cancel ${item.file.name}`}
          >
            <X className="size-4" />
          </button>
        )}
        {item.status === 'done' && (
          <CheckCircle2 className="size-5 text-green-600" aria-label="Uploaded" />
        )}
        {item.status === 'error' && <XCircle className="size-5 text-red-500" aria-label="Failed" />}
      </div>

      {(item.status === 'uploading' || item.status === 'done') && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full transition-all ${item.status === 'done' ? 'bg-green-500' : 'bg-blue-600'}`}
            style={{ width: `${item.progress}%` }}
          />
        </div>
      )}

      {item.status === 'error' && (
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <p className="text-xs text-red-600">{item.error}</p>
          {item.code === 'DUPLICATE_FILE' && (
            <button
              type="button"
              onClick={onKeepBoth}
              className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
            >
              <Copy className="size-3" /> Keep both
            </button>
          )}
          {item.code === 'CANCELLED' && (
            <button
              type="button"
              onClick={onRetry}
              className="text-xs font-medium text-blue-600 hover:underline"
            >
              Retry
            </button>
          )}
        </div>
      )}
    </li>
  );
}
