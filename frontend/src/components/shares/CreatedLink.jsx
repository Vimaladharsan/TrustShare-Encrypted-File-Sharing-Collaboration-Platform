import { Check, Copy, QrCode } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import Button from '../Button';
import LinkQrCode from './LinkQrCode';

/** A newly created share link: the URL, Copy, and an optional QR code. */
export default function CreatedLink({ url, fileName, showName = false }) {
  const [copied, setCopied] = useState(false);
  const [qr, setQr] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success('Link copied');
    } catch {
      toast.error('Copy failed – select the link and copy it manually.');
    }
  }

  return (
    <div>
      {showName && <p className="mb-1 truncate text-xs font-medium text-slate-700">{fileName}</p>}
      <div className="flex gap-2">
        <input
          readOnly
          value={url}
          onFocus={(e) => e.target.select()}
          aria-label={`Share link${fileName ? ` for ${fileName}` : ''}`}
          className="min-w-0 flex-1 rounded-lg border border-blue-200 bg-white px-3 py-2 font-mono text-xs"
        />
        <Button onClick={copy}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
        <Button
          variant="secondary"
          onClick={() => setQr((v) => !v)}
          aria-pressed={qr}
          aria-label={qr ? 'Hide QR code' : 'Show QR code'}
          title="QR code"
        >
          <QrCode className="size-4" aria-hidden="true" />
        </Button>
      </div>
      {qr && <LinkQrCode url={url} fileName={fileName} />}
    </div>
  );
}
