import { CloudUpload, Database, Download, Share2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { getAnalytics } from '../api/analytics';
import { getErrorMessage } from '../api/client';
import {
  DownloadsChart,
  SharesChart,
  StorageDonut,
  UploadsChart,
} from '../components/analytics/AnalyticsCharts';
import { DateRangeFilter, SummaryCard } from '../components/analytics/AnalyticsParts';
import { ErrorState, Loading } from '../components/StateMessage';
import { presetRange } from '../utils/charts';
import { fileIcon, formatBytes } from '../utils/format';

const VIA = { owner: 'Direct', direct_share: 'Shared with person', link: 'Share link' };

const dateTime = (iso) =>
  new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

/** File Analytics: real numbers about my storage, uploads, downloads and sharing. */
export default function AnalyticsPage() {
  const [range, setRange] = useState(() => presetRange(30));
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setError('');
    getAnalytics(range)
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)));
  }, [range]);

  useEffect(load, [load]);

  const s = data?.summary;
  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">File Analytics</h1>
          <p className="text-sm text-slate-500">
            Insights about your storage, uploads, downloads and sharing activity.
          </p>
        </div>
        <DateRangeFilter range={range} onChange={setRange} />
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <Loading />}
      {!error && data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryCard
              icon={Database}
              tone="bg-blue-50 text-blue-600"
              label="Total storage used"
              value={formatBytes(s.storage_used_bytes)}
              sub={`of ${formatBytes(s.quota_bytes)}`}
            />
            <SummaryCard
              icon={CloudUpload}
              tone="bg-green-50 text-green-600"
              label="Uploads"
              value={s.uploads.value}
              sub="files uploaded"
              metric={s.uploads}
            />
            <SummaryCard
              icon={Download}
              tone="bg-violet-50 text-violet-600"
              label="Downloads"
              value={s.downloads.value}
              sub="of your files"
              metric={s.downloads}
            />
            <SummaryCard
              icon={Share2}
              tone="bg-rose-50 text-rose-600"
              label="Shares"
              value={s.shares.value}
              sub="links and people"
              metric={s.shares}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <StorageDonut usage={data.storage_by_category} quotaBytes={s.quota_bytes} />
            <UploadsChart days={data.uploads_by_day} />
            <DownloadsChart days={data.downloads_by_day} />
            <SharesChart days={data.shares_by_day} />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <RecentTable
              title="Recent uploads"
              empty="No uploads yet."
              columns={['File', 'Size', 'Type', 'Date & time']}
              rows={data.recent_uploads.map((f) => ({
                key: f.id,
                name: f.name,
                category: f.category,
                cells: [
                  formatBytes(f.size_bytes),
                  f.extension.toUpperCase(),
                  dateTime(f.created_at),
                ],
              }))}
            />
            <RecentTable
              title="Recent downloads"
              empty="Nobody has downloaded your files yet."
              columns={['File', 'Downloaded by', 'Size', 'Date & time']}
              rows={data.recent_downloads.map((d, i) => ({
                key: `${d.file_id}-${i}`,
                name: d.file_name,
                category: d.category,
                cells: [
                  <span key="who" title={VIA[d.via]}>
                    {d.downloaded_by}
                  </span>,
                  d.size_bytes === null ? 'Deleted' : formatBytes(d.size_bytes),
                  dateTime(d.created_at),
                ],
              }))}
            />
          </div>
        </>
      )}
    </div>
  );
}

function RecentTable({ title, columns, rows, empty }) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 font-semibold text-slate-900">{title}</h2>
      {rows.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">{empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="px-3 py-2 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => {
                const { Icon, color } = fileIcon(row.category);
                return (
                  <tr key={row.key}>
                    <td className="max-w-[14rem] px-3 py-2">
                      <span className="flex items-center gap-2">
                        <Icon className={`size-4 shrink-0 ${color}`} aria-hidden="true" />
                        <span className="truncate text-slate-800" title={row.name}>
                          {row.name}
                        </span>
                      </span>
                    </td>
                    {row.cells.map((cell, i) => (
                      <td key={i} className="px-3 py-2 whitespace-nowrap text-slate-600">
                        {cell}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
