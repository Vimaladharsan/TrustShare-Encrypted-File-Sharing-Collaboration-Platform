import { Link } from 'react-router';

import { formatBytes } from '../../utils/format';

const RADIUS = 16;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Sidebar storage card: a ring with the percentage, "80 KB of 1 GB" and a link to Storage. */
export default function StorageMeter({ usage }) {
  if (!usage) return null;
  const percent = Math.min(100, (usage.used_bytes / usage.quota_bytes) * 100);
  const color = percent > 90 ? 'text-red-500' : percent > 70 ? 'text-amber-500' : 'text-blue-600';
  const shown = percent > 0 && percent < 1 ? '<1' : Math.round(percent);

  return (
    <Link
      to="/storage"
      className="group hover:shadow-card flex items-center gap-3 rounded-xl border border-slate-200/80 bg-gradient-to-br from-slate-50 to-white p-3 transition hover:border-slate-300"
    >
      <div
        className="relative size-11 shrink-0"
        role="progressbar"
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Storage used"
      >
        <svg viewBox="0 0 40 40" className="size-full -rotate-90">
          <circle
            cx="20"
            cy="20"
            r={RADIUS}
            fill="none"
            strokeWidth="4"
            className="stroke-slate-200"
          />
          <circle
            cx="20"
            cy="20"
            r={RADIUS}
            fill="none"
            strokeWidth="4"
            strokeLinecap="round"
            stroke="currentColor"
            className={`${color} transition-all duration-500`}
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={CIRCUMFERENCE * (1 - Math.max(percent, 1) / 100)}
          />
        </svg>
        <span className="absolute inset-0 grid place-items-center text-[10px] font-semibold text-slate-700">
          {shown}%
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-900">
          {formatBytes(usage.used_bytes)}
          <span className="font-normal text-slate-400"> / {formatBytes(usage.quota_bytes)}</span>
        </p>
        <p className="text-xs text-slate-500 group-hover:text-blue-600">Encrypted storage used</p>
      </div>
    </Link>
  );
}
