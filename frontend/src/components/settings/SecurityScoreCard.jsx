import { AlertCircle, ArrowRight, CheckCircle2, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { toast } from 'sonner';

import { resendVerification } from '../../api/auth';
import { getErrorMessage } from '../../api/client';
import Button from '../Button';

const GRADES = {
  strong: { label: 'Strong', ring: 'text-emerald-500', text: 'text-emerald-700' },
  good: { label: 'Good', ring: 'text-blue-500', text: 'text-blue-700' },
  needs_attention: { label: 'Needs attention', ring: 'text-amber-500', text: 'text-amber-700' },
};

/**
 * Account security score (0–100) with the checklist behind it. Every check that doesn't pass has a
 * "Fix now" button that opens the setting that fixes it. The score is calculated on the server.
 */
export default function SecurityScoreCard({ overview }) {
  const navigate = useNavigate();
  const [, setParams] = useSearchParams();
  const [sending, setSending] = useState(false);
  const grade = GRADES[overview.grade] || GRADES.good;
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const passed = overview.checks.filter((c) => c.ok).length;

  async function fix(check) {
    if (check.fix === 'security' || check.fix === 'devices') setParams({ tab: check.fix });
    else if (check.fix === 'activity') navigate('/activity');
    else if (check.fix === 'vault') navigate('/vault');
    else if (check.fix === 'verify_email') {
      setSending(true);
      try {
        await resendVerification();
        toast.success('Verification email sent – check your inbox');
      } catch (err) {
        toast.error(getErrorMessage(err));
      } finally {
        setSending(false);
      }
    }
  }

  return (
    <section className="card p-5 sm:p-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <div className="relative mx-auto size-28 shrink-0 sm:mx-0">
          <svg viewBox="0 0 100 100" className="size-28 -rotate-90" aria-hidden="true">
            <circle
              cx="50"
              cy="50"
              r={radius}
              className="fill-none stroke-slate-200"
              strokeWidth="9"
            />
            <circle
              cx="50"
              cy="50"
              r={radius}
              className={`fill-none stroke-current transition-all duration-700 ${grade.ring}`}
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - overview.score / 100)}
            />
          </svg>
          <div className="absolute inset-0 grid place-items-center text-center">
            <div>
              <p className="text-3xl font-bold text-slate-950 tabular-nums">{overview.score}</p>
              <p className="text-[11px] font-medium text-slate-500">of 100</p>
            </div>
          </div>
        </div>
        <div className="min-w-0 text-center sm:text-left">
          <p className="eyebrow flex items-center justify-center gap-1.5 sm:justify-start">
            <ShieldCheck className="size-3.5" aria-hidden="true" /> Account security score
          </p>
          <h2 className={`mt-1 text-xl font-semibold ${grade.text}`}>{grade.label}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {passed} of {overview.checks.length} protections in place.
            {overview.score < 100 && ' Fix the items below to raise your score.'}
          </p>
        </div>
      </div>

      <ul className="mt-5 divide-y divide-slate-100 rounded-xl border border-slate-200">
        {overview.checks.map((check) => (
          <li key={check.key} className="flex items-start gap-3 px-4 py-3">
            {check.ok ? (
              <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-500" aria-label="Done" />
            ) : (
              <AlertCircle className="mt-0.5 size-5 shrink-0 text-amber-500" aria-label="To do" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900">
                {check.label}{' '}
                <span
                  className={`ml-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                    check.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {check.ok ? `+${check.points}` : `${check.points} pts`}
                </span>
              </p>
              <p className="mt-0.5 text-xs text-slate-500">{check.detail}</p>
            </div>
            {!check.ok && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => fix(check)}
                loading={check.fix === 'verify_email' && sending}
              >
                {check.fix === 'verify_email' ? 'Resend email' : 'Fix now'}
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
