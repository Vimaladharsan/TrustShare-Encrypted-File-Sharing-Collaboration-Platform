import { HardDrive, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';

import { getStorageReport } from '../api/analytics';
import { getErrorMessage } from '../api/client';
import { ErrorState, Loading } from '../components/StateMessage';
import { CATEGORY_SERIES } from '../utils/charts';
import { formatBytes } from '../utils/format';
import FileIcon from '../components/files/FileIcon';

/** Storage: how much of my quota is used, by which file types, and what takes the most space. */
export default function StoragePage() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setError('');
    getStorageReport()
      .then(setReport)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!report) return <Loading />;

  const { used_bytes: used, quota_bytes: quota } = report;
  const percent = quota ? Math.min(100, (used / quota) * 100) : 0;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Storage</h1>
        <p className="mt-1 text-sm text-slate-500">
          Every file is stored encrypted. Files in the trash still count until deleted forever.
        </p>
      </div>

      <section className="card p-5">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div className="flex items-center gap-3">
            <span className="flex size-11 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <HardDrive className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-2xl font-semibold text-slate-900">{formatBytes(used)}</p>
              <p className="text-sm text-slate-500">
                used of {formatBytes(quota)} · {formatBytes(Math.max(quota - used, 0))} available
              </p>
            </div>
          </div>
          <span className="text-sm font-medium text-slate-700">{percent.toFixed(1)}%</span>
        </div>
        {/* One bar split by file type (with 2px gaps), then the legend with exact sizes. */}
        <div
          className="mt-4 flex h-3 gap-0.5 overflow-hidden rounded-full bg-slate-100"
          role="img"
          aria-label={`${percent.toFixed(1)}% of storage used`}
        >
          {CATEGORY_SERIES.map((s) => {
            const bytes = report.by_category.find((c) => c.category === s.key)?.bytes ?? 0;
            return bytes > 0 ? (
              <div
                key={s.key}
                style={{ width: `${(bytes / quota) * 100}%`, background: s.color, minWidth: 3 }}
                title={`${s.label}: ${formatBytes(bytes)}`}
              />
            ) : null;
          })}
        </div>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {CATEGORY_SERIES.map((s) => {
            const row = report.by_category.find((c) => c.category === s.key);
            return (
              <li key={s.key} className="rounded-lg bg-slate-50 p-3 text-sm">
                <span className="flex items-center gap-2 text-slate-600">
                  <span className="size-2.5 rounded-sm" style={{ background: s.color }} />
                  {s.label}
                </span>
                <p className="mt-1 font-semibold text-slate-900">{formatBytes(row?.bytes ?? 0)}</p>
                <p className="text-xs text-slate-500">
                  {row?.files ?? 0} file{row?.files === 1 ? '' : 's'}
                </p>
              </li>
            );
          })}
        </ul>
        {report.trash_bytes > 0 && (
          <p className="mt-4 flex items-center gap-2 text-sm text-slate-600">
            <Trash2 className="size-4 text-slate-400" aria-hidden="true" />
            {formatBytes(report.trash_bytes)} is in the trash.
            <Link to="/trash" className="font-medium text-blue-600 hover:underline">
              Free it up
            </Link>
          </p>
        )}
      </section>

      <section className="card p-5">
        <h2 className="mb-3 font-semibold text-slate-900">Largest files</h2>
        {report.largest.length === 0 ? (
          <p className="text-sm text-slate-500">No files yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {report.largest.map((file) => {
              return (
                <li key={file.id} className="flex items-center gap-3 py-2 text-sm">
                  <FileIcon category={file.category} size="sm" />
                  <span className="min-w-0 flex-1 truncate text-slate-800">{file.name}</span>
                  <span className="text-slate-600">{formatBytes(file.size_bytes)}</span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
