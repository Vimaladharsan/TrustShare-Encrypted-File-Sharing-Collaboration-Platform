import { Lock } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { getErrorMessage } from '../../api/client';
import {
  getDownloadStatistics,
  getFileStatistics,
  getSharingStatistics,
  getStorageAnalytics,
  getUserStorage,
} from '../../api/monitoring';
import { PageHeader, Panel } from '../../components/admin/AdminBits';
import { DataTable, DayChart, FilterBar } from '../../components/admin/MonitoringBits';
import { humanize } from '../../utils/monitoring';
import { StorageByUserChart } from '../../components/admin/StorageCharts';
import { ErrorState, Loading } from '../../components/StateMessage';
import { presetRange } from '../../utils/charts';
import { formatBytes } from '../../utils/format';

/** Storage Analytics: how much is stored, by whom, of what type – and how files are used. */
export default function AdminStoragePage() {
  const [filters, setFilters] = useState(() => presetRange(30));
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [storage, users, files, downloads, sharing] = await Promise.all([
        getStorageAnalytics(filters),
        getUserStorage(filters),
        getFileStatistics(filters),
        getDownloadStatistics(filters),
        getSharingStatistics(filters),
      ]);
      setData({ storage, users, files, downloads, sharing });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Storage analytics"
        text="Storage consumption, user-wise usage and file activity – calculated from the real file records."
      />
      <p className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">
        <Lock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        Admins see sizes, types and counts – never file names or contents.
      </p>
      <FilterBar value={filters} onChange={setFilters} show={['dates', 'user', 'fileType']} />

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <Loading />}
      {data && <Analytics data={data} />}
    </div>
  );
}

function Analytics({ data }) {
  const { storage, users, files, downloads, sharing } = data;
  const cards = [
    ['Total storage used', formatBytes(storage.total_bytes)],
    ['Files stored', storage.total_files],
    ['Uploaded (period)', files.uploaded],
    ['Downloaded (period)', downloads.total],
    ['Files shared (period)', files.shared_files],
    ['In trash', formatBytes(storage.trash_bytes)],
    ['In vaults', `${formatBytes(storage.vault_bytes)} · ${storage.vault_files} files`],
    ['Users with files', storage.users_with_files],
  ];
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {cards.map(([label, value]) => (
          <div key={label} className="card p-4">
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <p className="mt-1 text-xl font-semibold tracking-tight text-slate-950">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <StorageByUserChart users={users.items} />
        <DayChart title="File uploads by date (by type)" rows={files.uploads_by_day} />
        <DayChart title="File downloads (owner / shared / link)" rows={downloads.by_day} />
        <DayChart title="File sharing (link / direct)" rows={sharing.by_day} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Storage by type">
          <DataTable
            columns={['category', 'files', 'bytes']}
            rows={storage.by_category.filter((c) => c.files)}
            render={{ category: (value) => humanize(value) }}
          />
        </Panel>
        <Panel title="Most downloaded files">
          <DataTable
            columns={['file_id', 'extension', 'owner_email', 'downloads']}
            rows={downloads.most_downloaded}
            empty="No downloads in this period."
          />
        </Panel>
      </div>

      <Panel title="Storage used by each user">
        <DataTable
          columns={['full_name', 'email', 'role', 'files', 'bytes', 'vault_files', 'vault_bytes',
            'percent_used', 'last_upload_at']} // prettier-ignore
          rows={users.items}
          empty="No files stored yet."
          render={{
            percent_used: (value) => (
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full bg-blue-600"
                    style={{ width: `${Math.max(Math.min(value, 100), 1)}%` }}
                  />
                </div>
                <span className="text-xs text-slate-500">{value}%</span>
              </div>
            ),
          }}
        />
      </Panel>

      <div className="grid gap-5 md:grid-cols-3">
        <Panel title="Share status (period)">
          <DataTable
            columns={['status', 'count']}
            rows={['active', 'expired', 'revoked', 'used_up'].map((s) => ({
              status: humanize(s),
              count: sharing[s],
            }))}
          />
        </Panel>
        <Panel title="Top sharers">
          <DataTable columns={['email', 'count']} rows={sharing.by_owner} empty="No shares." />
        </Panel>
        <Panel title="Top recipients">
          <DataTable
            columns={['email', 'count']}
            rows={sharing.top_recipients}
            empty="No direct shares."
          />
        </Panel>
      </div>
    </div>
  );
}
