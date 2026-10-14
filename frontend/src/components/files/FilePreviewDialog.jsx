import { Download, EyeOff } from 'lucide-react';
import { useEffect, useState } from 'react';

import { getErrorMessage } from '../../api/client';
import { PREVIEWABLE, previewFile } from '../../api/files';
import { formatBytes } from '../../utils/format';
import Button from '../Button';
import Modal from '../Modal';
import { Empty, ErrorState, Loading } from '../StateMessage';

const MAX_TEXT_PREVIEW = 2 * 1024 * 1024; // bigger text files are faster to download than to show

/**
 * Shows a PDF, image or text file inside the app. The file is fetched with the login token and
 * displayed from memory (a blob: URL) – it is never saved to disk unless the user clicks Download.
 */
export default function FilePreviewDialog({ file, onDownload, onClose }) {
  const kind = previewKind(file);
  const [content, setContent] = useState(null); // { url } for PDF/images, { text } for text
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!kind) return undefined;
    const controller = new AbortController(); // cancels the request if the dialog closes
    let url = null;
    setContent(null);
    setError('');
    previewFile(file.id, controller.signal)
      .then(async (blob) => {
        if (kind === 'text') {
          setContent({ text: await blob.text() });
        } else {
          url = URL.createObjectURL(blob);
          setContent({ url });
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(getErrorMessage(err));
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url); // free the memory
    };
  }, [file.id, kind, attempt]);

  return (
    <Modal title={file.name} onClose={onClose} width="max-w-5xl">
      <div className="flex h-[70vh] items-center justify-center overflow-hidden rounded-lg bg-slate-100">
        {!kind && (
          <Empty
            icon={EyeOff}
            title="No preview for this file type"
            text={
              file.size_bytes > MAX_TEXT_PREVIEW && PREVIEWABLE.includes(file.extension)
                ? 'This text file is too large to preview.'
                : 'Word, Excel and PowerPoint files can be opened after downloading.'
            }
          />
        )}
        {kind && error && <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />}
        {kind && !error && !content && <Loading />}
        {content?.url && kind === 'pdf' && (
          <iframe src={content.url} title={`Preview of ${file.name}`} className="size-full" />
        )}
        {content?.url && kind === 'image' && (
          <img src={content.url} alt={file.name} className="max-h-full max-w-full object-contain" />
        )}
        {content?.text !== undefined && (
          <pre className="size-full overflow-auto bg-white p-4 text-left font-mono text-xs whitespace-pre-wrap text-slate-800">
            {content.text}
          </pre>
        )}
      </div>
      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm text-slate-500">
          {file.extension.toUpperCase()} · {formatBytes(file.size_bytes)}
        </span>
        <Button onClick={onDownload}>
          <Download className="size-4" aria-hidden="true" /> Download
        </Button>
      </div>
    </Modal>
  );
}

/** 'pdf' | 'image' | 'text', or null when the browser can't show this file. */
function previewKind(file) {
  if (!PREVIEWABLE.includes(file.extension)) return null;
  if (file.extension === 'pdf') return 'pdf';
  if (['png', 'jpg', 'jpeg'].includes(file.extension)) return 'image';
  return file.size_bytes <= MAX_TEXT_PREVIEW ? 'text' : null;
}
