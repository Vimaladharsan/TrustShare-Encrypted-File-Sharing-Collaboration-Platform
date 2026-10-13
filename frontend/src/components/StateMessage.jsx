import { AlertCircle, Loader2 } from 'lucide-react';

import Button from './Button';

/** The loading / empty / error states every list needs. */
export function Loading() {
  return (
    <div className="flex justify-center py-16 text-slate-400">
      <Loader2 className="size-6 animate-spin" aria-label="Loading" />
    </div>
  );
}

export function Empty({ icon: Icon, title, text, children }) {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      {Icon && <Icon className="size-12 text-slate-300" aria-hidden="true" />}
      <p className="mt-3 font-medium text-slate-700">{title}</p>
      {text && <p className="mt-1 text-sm text-slate-500">{text}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      <AlertCircle className="size-10 text-red-400" aria-hidden="true" />
      <p className="mt-3 text-sm text-slate-600">{message}</p>
      <Button variant="secondary" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
