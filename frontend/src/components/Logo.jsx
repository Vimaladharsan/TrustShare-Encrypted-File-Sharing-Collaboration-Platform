import { ShieldCheck } from 'lucide-react';

export default function Logo({ className = '' }) {
  return (
    <div className={`flex items-center gap-2 font-semibold text-slate-900 ${className}`}>
      <span className="grid size-8 place-items-center rounded-lg bg-blue-600 text-white">
        <ShieldCheck className="size-5" aria-hidden="true" />
      </span>
      <span className="text-lg tracking-tight">TrustShare</span>
    </div>
  );
}
