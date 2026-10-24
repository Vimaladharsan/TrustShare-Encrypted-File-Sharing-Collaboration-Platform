import { ShieldCheck } from 'lucide-react';

/** variant="light" for dark backgrounds (the auth showcase panel, the admin sidebar). */
export default function Logo({ className = '', variant = 'dark' }) {
  const text = variant === 'light' ? 'text-white' : 'text-slate-950';
  return (
    <div className={`flex items-center gap-2.5 font-semibold ${text} ${className}`}>
      <span className="grid size-8 place-items-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-md ring-1 shadow-blue-600/30 ring-white/20 ring-inset">
        <ShieldCheck className="size-[18px]" aria-hidden="true" />
      </span>
      <span className="text-[17px] tracking-tight">TrustShare</span>
    </div>
  );
}
