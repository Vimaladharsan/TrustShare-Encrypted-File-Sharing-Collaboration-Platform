import { Download } from 'lucide-react';
import QRCode from 'qrcode';
import { useEffect, useState } from 'react';

import Button from '../Button';

/**
 * QR code for a share link, drawn in the browser by the `qrcode` library. The link is a secret,
 * so it is never sent to an online QR service. Download saves it as a PNG (e.g. for a slide).
 */
export default function LinkQrCode({ url, fileName }) {
  const [image, setImage] = useState('');

  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(url, { width: 480, margin: 2, errorCorrectionLevel: 'M' })
      .then((dataUrl) => alive && setImage(dataUrl))
      .catch(() => alive && setImage(''));
    return () => {
      alive = false;
    };
  }, [url]);

  function download() {
    const link = document.createElement('a');
    link.href = image;
    link.download = `${(fileName || 'trustshare-link').replace(/\.[^.]+$/, '')}-share-qr.png`;
    link.click();
  }

  if (!image) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-4">
      {/* Always dark-on-white, so phones can scan it in dark mode too. */}
      <img
        src={image}
        alt="QR code of the share link"
        className="size-36 rounded-lg bg-[#ffffff] p-1 ring-1 ring-slate-200"
      />
      <div className="min-w-0 flex-1 space-y-2 text-xs text-slate-600">
        <p>Scan with a phone camera to open the link.</p>
        <p>Anyone who scans it gets the same access as the link – share it like the link itself.</p>
        <Button size="sm" variant="secondary" onClick={download}>
          <Download className="size-3.5" aria-hidden="true" /> Download QR (PNG)
        </Button>
      </div>
    </div>
  );
}
