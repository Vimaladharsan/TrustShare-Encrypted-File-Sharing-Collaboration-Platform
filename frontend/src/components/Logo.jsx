import { ShieldCheck } from 'lucide-react';

/** variant="light" for dark backgrounds (the auth showcase panel). */
export default function Logo({ className = '', variant = 'dark' }) {
  const text = variant === 'light' ? 'text-white' : 'text-slate-900';
  return (
    <div className={`flex items-center gap-2 font-semibold ${text} ${className}`}>
      <span className="grid size-8 place-items-center rounded-lg bg-blue-600 text-white">
        <ShieldCheck className="size-5" aria-hidden="true" />
      </span>
      <span className="text-lg tracking-tight">TrustShare</span>
    </div>
  );
}
