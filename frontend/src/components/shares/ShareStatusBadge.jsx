/** Coloured label for a share's state (Share dialog, "Shared by me"). */

const STATUS = {
  active: { label: 'Active', className: 'bg-green-50 text-green-700' },
  expired: { label: 'Expired', className: 'bg-slate-100 text-slate-600' },
  revoked: { label: 'Revoked', className: 'bg-red-50 text-red-700' },
  used_up: { label: 'Limit reached', className: 'bg-amber-50 text-amber-700' },
  file_unavailable: { label: 'File in trash', className: 'bg-slate-100 text-slate-600' },
};

export default function ShareStatusBadge({ status }) {
  const { label, className } = STATUS[status] || STATUS.expired;
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}
