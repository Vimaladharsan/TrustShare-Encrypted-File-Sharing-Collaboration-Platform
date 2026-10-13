import { formatBytes } from '../../utils/format';

/** "236 MB of 1 GB used" with a progress bar (red when almost full). */
export default function StorageMeter({ usage }) {
  if (!usage) return null;
  const percent = Math.min(100, (usage.used_bytes / usage.quota_bytes) * 100);
  const bar = percent > 90 ? 'bg-red-500' : percent > 70 ? 'bg-amber-500' : 'bg-blue-600';

  return (
    <div className="px-2">
      <p className="text-xs font-medium text-slate-500">Storage</p>
      <div
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Storage used"
      >
        <div className={`h-full ${bar}`} style={{ width: `${Math.max(percent, 1)}%` }} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {formatBytes(usage.used_bytes)} of {formatBytes(usage.quota_bytes)} used
      </p>
    </div>
  );
}
