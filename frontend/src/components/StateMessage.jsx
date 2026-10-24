import { AlertCircle } from 'lucide-react';

import Button from './Button';

/** The loading / empty / error states every list needs. */

/** Skeleton rows while data loads – the layout doesn't jump when the content arrives. */
export function Loading({ rows = 4 }) {
  return (
    <div className="space-y-3 py-2" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="card flex items-center gap-4 p-4">
          <div className="size-10 shrink-0 animate-pulse rounded-xl bg-slate-100" />
          <div className="flex-1 space-y-2">
            <div
              className="h-3 animate-pulse rounded-full bg-slate-100"
              style={{ width: `${60 - i * 8}%` }}
            />
            <div className="h-2.5 w-1/4 animate-pulse rounded-full bg-slate-100" />
          </div>
        </div>
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function Empty({ icon: Icon, title, text, children }) {
  return (
    <div className="flex flex-col items-center px-4 py-16 text-center">
      {Icon && (
        <div className="relative">
          <div className="absolute inset-0 -z-10 scale-150 rounded-full bg-blue-100/40 blur-2xl" />
          <span className="shadow-card grid size-14 place-items-center rounded-2xl bg-white ring-1 ring-slate-200">
            <Icon className="size-6 text-slate-400" aria-hidden="true" />
          </span>
        </div>
      )}
      <p className="mt-4 text-base font-semibold text-slate-900">{title}</p>
      {text && <p className="mt-1 max-w-sm text-sm text-slate-500">{text}</p>}
      {children && <div className="mt-5">{children}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center px-4 py-16 text-center">
      <span className="grid size-14 place-items-center rounded-2xl bg-red-50 ring-1 ring-red-100">
        <AlertCircle className="size-6 text-red-500" aria-hidden="true" />
      </span>
      <p className="mt-4 text-base font-semibold text-slate-900">Something went wrong</p>
      <p className="mt-1 max-w-sm text-sm text-slate-500">{message}</p>
      <Button variant="secondary" className="mt-5" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
