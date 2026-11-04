import { Ban, Download, Eye, Monitor, MousePointerClick, Smartphone } from 'lucide-react';
import { useEffect, useState } from 'react';

import { getErrorMessage } from '../../api/client';
import { getShareAccess } from '../../api/shares';
import { formatDate, timeAgo } from '../../utils/format';
import Modal from '../Modal';
import { ErrorState, Loading } from '../StateMessage';

const EVENTS = {
  opened: {
    label: 'Opened the link',
    icon: MousePointerClick,
    tone: 'bg-slate-100 text-slate-600',
  },
  viewed: { label: 'Viewed', icon: Eye, tone: 'bg-blue-50 text-blue-600' },
  downloaded: { label: 'Downloaded', icon: Download, tone: 'bg-emerald-50 text-emerald-600' },
  refused: { label: 'Refused', icon: Ban, tone: 'bg-red-50 text-red-600' },
};

const SUMMARY = [
  ['opened', 'Opened'],
  ['viewed', 'Viewed'],
  ['downloaded', 'Downloaded'],
  ['refused', 'Refused'],
  ['visitors', 'Visitors'],
];

/**
 * Access history of one share: who opened, viewed or downloaded it, when, from which device –
 * and refused attempts with the reason (expired, revoked, limit reached …). Owner only.
 * Visitors' IP addresses are shown with the last part hidden.
 */
export default function AccessHistoryDialog({ share, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    getShareAccess(share.id)
      .then((result) => alive && setData(result))
      .catch((err) => alive && setError(getErrorMessage(err)));
    return () => {
      alive = false;
    };
  }, [share.id]);

  const target = share.share_type === 'link' ? 'Anyone with the link' : share.recipient_email;

  return (
    <Modal title="Access history" onClose={onClose} width="max-w-2xl">
      <p className="-mt-2 mb-4 truncate text-sm text-slate-500">
        “{share.file_name}” · {target}
      </p>

      {error && <ErrorState message={error} />}
      {!error && !data && <Loading rows={3} />}
      {data && (
        <>
          <div className="mb-4 grid grid-cols-5 gap-2">
            {SUMMARY.map(([key, label]) => (
              <div key={key} className="rounded-lg border border-slate-200 px-3 py-2">
                <p className="text-[11px] font-medium text-slate-500">{label}</p>
                <p className="text-lg font-semibold text-slate-900 tabular-nums">
                  {data.summary[key]}
                </p>
              </div>
            ))}
          </div>

          {data.items.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 py-8 text-center text-sm text-slate-500">
              Nobody has used this share yet.
            </p>
          ) : (
            <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
              {data.items.map((item, index) => {
                const event = EVENTS[item.event];
                const DeviceIcon = item.kind === 'mobile' ? Smartphone : Monitor;
                return (
                  <li key={`${item.at}-${index}`} className="flex items-start gap-3 px-3 py-2.5">
                    <span
                      className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${event.tone}`}
                    >
                      <event.icon className="size-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-900">
                        {event.label}
                        {item.detail && (
                          <span className="font-normal text-red-600"> – {item.detail}</span>
                        )}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {item.visitor}
                        {item.visitor_email && item.visitor !== item.visitor_email
                          ? ` (${item.visitor_email})`
                          : ''}
                      </p>
                      <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-400">
                        <DeviceIcon className="size-3.5" aria-hidden="true" />
                        {item.device}
                        {item.ip && <span>· IP {item.ip}</span>}
                      </p>
                    </div>
                    <span
                      className="shrink-0 text-right text-xs text-slate-500"
                      title={`${formatDate(item.at)}, ${new Date(item.at).toLocaleTimeString('en-GB')}`}
                    >
                      {timeAgo(item.at)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="mt-3 text-xs text-slate-400">
            Newest first. Visitors&apos; IP addresses are shown with the last part hidden.
          </p>
        </>
      )}
    </Modal>
  );
}
