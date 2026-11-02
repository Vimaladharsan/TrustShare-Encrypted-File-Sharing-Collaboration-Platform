import { BellOff, CheckCheck } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import { listNotifications } from '../api/notifications';
import Button from '../components/Button';
import NotificationItem from '../components/notifications/NotificationItem';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import { TYPE_LABELS } from '../notifications/types';
import { useNotifications } from '../notifications/useNotifications';

const PAGE = 20;

/** Notification history: filters (all / unread, type), load more, mark read. */
export default function NotificationsPage() {
  const { unread, version, markOne, markAll } = useNotifications();
  const [filter, setFilter] = useState({ unread: false, type: '' });
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');
  const [loadingMore, setLoadingMore] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setError('');
    try {
      const page = await listNotifications({ ...filter, limit: PAGE });
      setItems(page.items);
      setTotal(page.total);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load, version]); // reloads when a live notification arrives or something is marked read

  async function loadMore() {
    setLoadingMore(true);
    try {
      const page = await listNotifications({ ...filter, limit: PAGE, offset: items.length });
      setItems((current) => [...current, ...page.items]);
      setTotal(page.total);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  }

  async function open(item) {
    try {
      if (!item.read) await markOne(item.id);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
    if (item.link) navigate(item.link);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Notifications</h1>
          <p className="mt-1 text-sm text-slate-500">
            {unread ? `${unread} unread` : 'All caught up'} · arrive live, also by email where you
            chose it
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={!unread}
          onClick={() => markAll().catch((err) => toast.error(getErrorMessage(err)))}
        >
          <CheckCheck className="size-4" aria-hidden="true" /> Mark all read
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-lg bg-slate-100 p-1 text-sm font-medium">
          {[
            [false, 'All'],
            [true, 'Unread'],
          ].map(([value, label]) => (
            <button
              key={label}
              type="button"
              onClick={() => setFilter((f) => ({ ...f, unread: value }))}
              className={`rounded-md px-3 py-1.5 ${
                filter.unread === value ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          value={filter.type}
          onChange={(e) => setFilter((f) => ({ ...f, type: e.target.value }))}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          aria-label="Notification type"
        >
          <option value="">All types</option>
          {Object.entries(TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && items === null && <Loading />}
      {!error && items?.length === 0 && (
        <Empty
          icon={BellOff}
          title={filter.unread ? 'No unread notifications' : 'No notifications yet'}
          text="Shares, downloads of your shared files, expiry reminders and security events appear here."
        />
      )}
      {!error && items?.length > 0 && (
        <section className="card divide-y divide-slate-100 p-2">
          {items.map((item) => (
            <NotificationItem key={item.id} item={item} onOpen={open} />
          ))}
        </section>
      )}
      {items && items.length < total && (
        <div className="flex justify-center">
          <Button variant="secondary" onClick={loadMore} loading={loadingMore}>
            Load more ({total - items.length} left)
          </Button>
        </div>
      )}
    </div>
  );
}
