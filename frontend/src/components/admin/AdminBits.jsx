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
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {text && <p className="text-sm text-slate-500">{text}</p>}
      </div>
      {children}
    </div>
  );
}

/** A white card with a title, used for the admin tables. */
export function Panel({ title, action, children }) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/** rows: [[key, ...cells]] */
export function Table({ head, rows, empty }) {
  if (rows.length === 0) return <p className="py-8 text-center text-sm text-slate-500">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-slate-50 text-xs text-slate-500">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {rows.map(([key, ...cells]) => (
            <tr key={key}>
              {cells.map((cell, i) => (
                <td key={i} className="px-3 py-2">
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
