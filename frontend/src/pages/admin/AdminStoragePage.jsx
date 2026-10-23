import { Lock } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { getSystemOverview } from '../../api/adminReports';
import { getErrorMessage } from '../../api/client';
import { PageHeader, Panel, Table } from '../../components/admin/AdminBits';
import { ErrorState, Loading } from '../../components/StateMessage';
import { presetRange } from '../../utils/charts';
import { formatBytes } from '../../utils/format';

/** File Management for admins: how much each account stores. Names and contents stay private. */
export default function AdminStoragePage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setError('');
    getSystemOverview(presetRange(7))
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <Loading />;
  return (
    <div className="space-y-5">
      <PageHeader
        title="File management"
        text={`${data.total_files} encrypted files, ${formatBytes(data.total_bytes)} in total.`}
      />
      <p className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">
        <Lock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        Admins see how much each account stores, but never file names or contents. Accounts inactive
        for 30+ days can be deleted (with their files) on the Users page.
      </p>
      <Panel title="Storage by account (largest first)">
        <Table
          empty="No files stored yet."
          head={['User', 'Email', 'Files', 'Stored', 'Quota used']}
          rows={data.storage_by_user.map((u) => {
            const percent = u.quota_bytes ? Math.min(100, (u.bytes / u.quota_bytes) * 100) : 0;
            return [
              u.user_id,
              u.full_name || <span className="text-slate-400">Deleted account</span>,
              u.email || '—',
              u.files,
              formatBytes(u.bytes),
              <div key="q" className="flex items-center gap-2">
                <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full bg-blue-600"
                    style={{ width: `${Math.max(percent, 1)}%` }}
                  />
                </div>
                <span className="text-xs text-slate-500">{percent.toFixed(1)}%</span>
              </div>,
            ];
          })}
        />
      </Panel>
    </div>
  );
}
