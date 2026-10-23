import { Download, Link2, Link2Off, UserRound, UserX } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { getSystemOverview } from '../../api/adminReports';
import { getErrorMessage } from '../../api/client';
import { PageHeader } from '../../components/admin/AdminBits';
import { SummaryCard } from '../../components/analytics/AnalyticsParts';
import { ErrorState, Loading } from '../../components/StateMessage';
import { presetRange } from '../../utils/charts';

/** Sharing Reports: how sharing is used across the platform (counts only). */
export default function AdminSharingPage() {
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
  const s = data.shares;
  return (
    <div className="space-y-5">
      <PageHeader
        title="Sharing reports"
        text="Share links and direct shares across all accounts. Ended = expired, revoked or used up."
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <SummaryCard
          icon={Link2}
          tone="bg-blue-50 text-blue-600"
          label="Active share links"
          value={s.links_active}
          sub="anyone with the link"
        />
        <SummaryCard
          icon={Link2Off}
          tone="bg-slate-100 text-slate-600"
          label="Ended share links"
          value={s.links_ended}
          sub="no longer work"
        />
        <SummaryCard
          icon={Download}
          tone="bg-violet-50 text-violet-600"
          label="Downloads through links"
          value={s.link_downloads}
          sub="all time"
        />
        <SummaryCard
          icon={UserRound}
          tone="bg-green-50 text-green-600"
          label="Active direct shares"
          value={s.direct_active}
          sub="with registered users"
        />
        <SummaryCard
          icon={UserX}
          tone="bg-slate-100 text-slate-600"
          label="Ended direct shares"
          value={s.direct_ended}
          sub="expired or revoked"
        />
      </div>
    </div>
  );
}
