import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Info,
  ShieldAlert,
  XCircle,
} from 'lucide-react';

// Small shared pieces of the admin pages: severity and login-status badges, date-time text.

const SEVERITY = {
  high: { label: 'High', icon: AlertOctagon, className: 'bg-red-50 text-red-700' },
  medium: { label: 'Medium', icon: AlertTriangle, className: 'bg-orange-50 text-orange-700' },
  low: { label: 'Low', icon: ShieldAlert, className: 'bg-amber-50 text-amber-800' },
  info: { label: 'Info', icon: Info, className: 'bg-blue-50 text-blue-700' },
};

/** Severity always shows an icon and a word – never colour alone. */
export function SeverityBadge({ severity }) {
  const { label, icon: Icon, className } = SEVERITY[severity] || SEVERITY.info;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${className}`}
    >
      <Icon className="size-3" aria-hidden="true" />
      {label}
    </span>
  );
}

export function LoginStatusBadge({ status }) {
  const ok = status === 'success';
  const Icon = ok ? CheckCircle2 : XCircle;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
      }`}
    >
      <Icon className="size-3" aria-hidden="true" />
      {ok ? 'Success' : 'Failed'}
    </span>
  );
}

export function DateTime({ value }) {
  return (
    <span className="whitespace-nowrap">
      {new Date(value).toLocaleString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })}
    </span>
  );
}

export function PageHeader({ title, text, children }) {
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="eyebrow mb-1 !text-blue-600">Administration</p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">{title}</h1>
        {text && <p className="mt-1 text-sm text-slate-500">{text}</p>}
      </div>
      {children}
    </div>
  );
}

/** A white card with a title, used for the admin tables. */
export function Panel({ title, action, children }) {
  return (
    <section className="card min-w-0 overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <h2 className="font-semibold text-slate-950">{title}</h2>
        {action}
      </div>
      <div className="p-2">{children}</div>
    </section>
  );
}

/** rows: [[key, ...cells]] */
export function Table({ head, rows, empty }) {
  if (rows.length === 0) return <p className="py-8 text-center text-sm text-slate-500">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2.5 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {rows.map(([key, ...cells]) => (
            <tr key={key} className="transition-colors hover:bg-slate-50/80">
              {cells.map((cell, i) => (
                <td key={i} className="px-3 py-2.5">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
