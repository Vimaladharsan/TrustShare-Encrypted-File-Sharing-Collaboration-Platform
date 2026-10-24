import { Clock, Download, Eye, Link2Off, Lock, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import { downloadPublic, getPublicShare, previewPublic } from '../api/shares';
import Button from '../components/Button';
import FilePreviewDialog from '../components/files/FilePreviewDialog';
import FileIcon from '../components/files/FileIcon';
import Logo from '../components/Logo';
import { Loading } from '../components/StateMessage';
import { formatBytes } from '../utils/format';
import { expiryLabel } from '../utils/shares';

const ENDED = {
  SHARE_EXPIRED: { icon: Clock, title: 'This link has expired' },
  SHARE_REVOKED: { icon: Link2Off, title: 'This link was revoked by its owner' },
  SHARE_LIMIT_REACHED: { icon: Lock, title: 'This link has reached its download limit' },
};

/**
 * What someone sees when they open a share link (/s/<token>). No account needed. The token is in
 * the URL path only – it is never sent to other sites (no-referrer) and never logged in clear.
 */
export default function PublicSharePage() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [failure, setFailure] = useState(null); // { code, message }
  const [previewing, setPreviewing] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    // Don't leak the link to other sites through the Referer header.
    const meta = document.createElement('meta');
    meta.name = 'referrer';
    meta.content = 'no-referrer';
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);

  useEffect(() => {
    getPublicShare(token)
      .then(setInfo)
      .catch((err) =>
        setFailure({
          code: err.response?.data?.error?.code || 'ERROR',
          message: getErrorMessage(err),
        }),
      );
  }, [token]);

  async function download() {
    setDownloading(true);
    try {
      await downloadPublic(token, info.file_name);
      const fresh = await getPublicShare(token).catch(() => null); // downloads left changed
      if (fresh) setInfo(fresh);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-slate-50">
      {/* Soft brand glow behind the card – decoration only. */}
      <div className="pointer-events-none absolute -top-40 left-1/2 size-[640px] -translate-x-1/2 rounded-full bg-gradient-to-br from-blue-200/50 to-indigo-200/40 blur-3xl" />
      <header className="relative flex items-center justify-between px-6 py-5">
        <Link to="/" aria-label="TrustShare home">
          <Logo />
        </Link>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 shadow-xs ring-1 ring-slate-200 backdrop-blur">
          <ShieldCheck className="size-3.5 text-emerald-600" aria-hidden="true" /> Secure link
        </span>
      </header>

      <main className="relative flex flex-1 items-center justify-center p-4">
        <div className="animate-pop-in shadow-pop w-full max-w-md rounded-3xl bg-white/90 p-8 ring-1 ring-slate-900/5 backdrop-blur">
          {!info && !failure && <Loading />}
          {failure && <Failure failure={failure} />}
          {info && (
            <SharedFile
              info={info}
              downloading={downloading}
              onPreview={() => setPreviewing(true)}
              onDownload={download}
            />
          )}
        </div>
      </main>

      <footer className="relative flex items-center justify-center gap-2 p-6 text-xs text-slate-500">
        <ShieldCheck className="size-4 text-emerald-600" aria-hidden="true" />
        Shared securely with TrustShare – stored encrypted with AES-256-GCM
      </footer>

      {previewing && info && (
        <FilePreviewDialog
          file={{
            id: token,
            name: info.file_name,
            extension: info.extension,
            size_bytes: info.size_bytes,
          }}
          load={(signal) => previewPublic(token, signal)}
          onDownload={info.permission === 'download' ? download : undefined}
          onClose={() => setPreviewing(false)}
        />
      )}
    </div>
  );
}

function SharedFile({ info, downloading, onPreview, onDownload }) {
  const canDownload = info.permission === 'download' && info.downloads_left !== 0;
  return (
    <div className="text-center">
      <div className="flex justify-center">
        <FileIcon category={info.category} size="lg" />
      </div>
      <p className="eyebrow mt-5">{info.owner_name} shared a file with you</p>
      <h1 className="mt-1.5 text-xl font-semibold tracking-tight break-words text-slate-950">
        {info.file_name}
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        {info.extension.toUpperCase()} · {formatBytes(info.size_bytes)}
      </p>

      <dl className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-slate-200/70 text-left text-xs ring-1 ring-slate-200/70 [&>div]:bg-slate-50 [&>div]:p-3">
        <div>
          <dt className="text-slate-500">Access</dt>
          <dd className="font-medium text-slate-800">
            {info.permission === 'download' ? 'View & download' : 'View only'}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Expires</dt>
          <dd className="font-medium text-slate-800">{expiryLabel(info.expires_at)}</dd>
        </div>
        {info.downloads_left !== null && (
          <div className="col-span-2">
            <dt className="text-slate-500">Downloads left</dt>
            <dd className="font-medium text-slate-800">{info.downloads_left}</dd>
          </div>
        )}
      </dl>

      <div className="mt-6 grid gap-2 sm:auto-cols-fr sm:grid-flow-col">
        {info.can_preview && (
          <Button variant="secondary" size="lg" onClick={onPreview}>
            <Eye className="size-4" aria-hidden="true" /> Preview
          </Button>
        )}
        {canDownload && (
          <Button size="lg" onClick={onDownload} loading={downloading}>
            <Download className="size-4" aria-hidden="true" /> Download
          </Button>
        )}
      </div>
      {info.permission === 'view' && !info.can_preview && (
        <p className="mt-4 text-sm text-slate-500">This file can&apos;t be shown in the browser.</p>
      )}
    </div>
  );
}

function Failure({ failure }) {
  const ended = ENDED[failure.code];
  const Icon = ended?.icon || Link2Off;
  return (
    <div className="py-6 text-center">
      <Icon className="mx-auto size-12 text-slate-300" aria-hidden="true" />
      <h1 className="mt-3 text-lg font-semibold text-slate-900">
        {ended?.title || 'This link is not available'}
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        {ended
          ? 'Ask the person who shared it for a new link.'
          : failure.code === 'SHARE_NOT_FOUND'
            ? 'The link is wrong, or the file is no longer shared.'
            : failure.message}
      </p>
    </div>
  );
}
