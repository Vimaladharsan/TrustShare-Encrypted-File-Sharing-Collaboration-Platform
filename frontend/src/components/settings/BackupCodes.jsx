import { Check, Copy, Download } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import Button from '../Button';

/** One-time backup codes with Copy / Download and an "I have saved them" check. */
export default function BackupCodes({ codes, onDone, intro }) {
  const [saved, setSaved] = useState(false);
  const text = codes.join('\n');

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Backup codes copied.');
    } catch {
      toast.error('Could not copy – please write the codes down.');
    }
  }

  function download() {
    const blob = new Blob([`TrustShare backup codes\n\n${text}\n`], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'trustshare-backup-codes.txt';
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        {intro || 'Two-step verification is on.'} If you lose your phone, each of these codes lets
        you log in <strong>once</strong>. They won&apos;t be shown again – keep them somewhere safe.
      </p>
      <ul className="grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-4 font-mono text-sm text-slate-800 ring-1 ring-slate-200 ring-inset">
        {codes.map((backupCode) => (
          <li key={backupCode}>{backupCode}</li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Button variant="secondary" onClick={copy}>
          <Copy className="size-4" aria-hidden="true" /> Copy
        </Button>
        <Button variant="secondary" onClick={download}>
          <Download className="size-4" aria-hidden="true" /> Download
        </Button>
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
          className="size-4 rounded border-slate-300"
        />
        I have saved my backup codes
      </label>
      <div className="flex justify-end">
        <Button onClick={onDone} disabled={!saved}>
          <Check className="size-4" aria-hidden="true" /> Done
        </Button>
      </div>
    </div>
  );
}
