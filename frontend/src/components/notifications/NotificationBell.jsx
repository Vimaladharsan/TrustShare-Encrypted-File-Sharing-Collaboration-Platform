import { Bell, CheckCheck, Settings } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { useNotifications } from '../../notifications/useNotifications';
import NotificationItem from './NotificationItem';

/** Bell in the top bar: unread badge, live dot, and the latest notifications in a dropdown. */
export default function NotificationBell() {
  const { unread, recent, live, markOne, markAll } = useNotifications();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => ref.current && !ref.current.contains(event.target) && setOpen(false);
    const onKey = (event) => event.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  async function openItem(item) {
    setOpen(false);
    try {
      if (!item.read) await markOne(item.id);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
    if (item.link) navigate(item.link);
  }

  return (
    <div className="relative ml-auto" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        className="relative grid size-10 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
      >
        <Bell className="size-5" aria-hidden="true" />
        {unread > 0 && (
          <span className="absolute top-1 right-1 grid min-w-[18px] place-items-center rounded-full bg-red-600 px-1 text-[10px] leading-[18px] font-bold text-white ring-2 ring-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="animate-pop-in shadow-pop absolute right-0 z-40 mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-2xl bg-white ring-1 ring-slate-900/5">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div>
              <p className="font-semibold text-slate-950">Notifications</p>
              <p className="flex items-center gap-1.5 text-xs text-slate-500">
                <span
                  className={`size-1.5 rounded-full ${live ? 'bg-emerald-500' : 'bg-slate-300'}`}
                  aria-hidden="true"
                />
                {live ? 'Live' : 'Connecting…'}
                {unread > 0 && ` · ${unread} unread`}
              </p>
            </div>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markAll().catch((err) => toast.error(getErrorMessage(err)))}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50"
              >
                <CheckCheck className="size-3.5" aria-hidden="true" /> Mark all read
              </button>
            )}
          </div>
          <div className="max-h-[60vh] overflow-y-auto p-2">
            {recent.length === 0 ? (
              <p className="px-3 py-10 text-center text-sm text-slate-500">
                You&apos;re all caught up.
              </p>
            ) : (
              recent.map((item) => (
                <NotificationItem key={item.id} item={item} onOpen={openItem} compact />
              ))
            )}
          </div>
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2.5 text-sm">
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              className="font-medium text-blue-700 hover:underline"
            >
              View all
            </Link>
            <Link
              to="/settings?tab=notifications"
              onClick={() => setOpen(false)}
              className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-800"
            >
              <Settings className="size-3.5" aria-hidden="true" /> Preferences
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
