import { Bell, Clock, Download, Share2, ShieldAlert, Siren, TimerOff } from 'lucide-react';

import { TYPE_LABELS } from '../../notifications/types';
import { formatDate, timeAgo } from '../../utils/format';

const ICONS = {
  file_shared: Share2,
  file_downloaded: Download,
  link_expiring: Clock,
  link_expired: TimerOff,
  account_security: ShieldAlert,
  security_alert: Siren,
};

const TONES = {
  critical: 'bg-red-50 text-red-600 ring-red-100',
  warning: 'bg-amber-50 text-amber-600 ring-amber-100',
  info: 'bg-blue-50 text-blue-600 ring-blue-100',
};

/** One notification: icon by type, colour by severity, unread dot, title, message and time. */
export default function NotificationItem({ item, onOpen, compact = false }) {
  const Icon = ICONS[item.type] || Bell;
  return (
    <button
      type="button"
      onClick={() => onOpen(item)}
      className={`flex w-full gap-3 rounded-lg text-left transition hover:bg-slate-50 ${
        compact ? 'p-2.5' : 'p-3'
      } ${item.read ? '' : 'bg-blue-50/40'}`}
    >
      <span
        className={`grid size-9 shrink-0 place-items-center rounded-lg ring-1 ring-inset ${
          TONES[item.severity] || TONES.info
        }`}
      >
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-start justify-between gap-2">
          <span
            className={`text-sm ${item.read ? 'font-medium text-slate-700' : 'font-semibold text-slate-950'}`}
          >
            {item.title}
          </span>
          {!item.read && (
            <span className="mt-1.5 size-2 shrink-0 rounded-full bg-blue-600" aria-label="Unread" />
          )}
        </span>
        <span className={`mt-0.5 block text-sm text-slate-600 ${compact ? 'line-clamp-2' : ''}`}>
          {item.message}
        </span>
        <span className="mt-1 block text-xs text-slate-400" title={formatDate(item.created_at)}>
          {timeAgo(item.created_at)}
          {!compact && ` · ${TYPE_LABELS[item.type] || item.type}`}
        </span>
      </span>
    </button>
  );
}
