import { CircleAlert, CircleCheck, Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { verifyEmail } from '../api/auth';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../auth/useAuth';
import AuthLayout from '../components/AuthLayout';

/** The page the sign-up email links to (/verify-email?token=...). Verifies automatically. */
export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const { status: authStatus, refreshUser } = useAuth();
  const [state, setState] = useState(token ? 'working' : 'error'); // working | done | error
  const [error, setError] = useState(token ? '' : 'This verification link is incomplete.');
  // The link works only once, and React StrictMode runs effects twice in development –
  // remember that we already sent it, so the second run doesn't report "link used up".
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    verifyEmail(token)
      .then(() => setState('done'))
      .catch((err) => {
        setError(getErrorMessage(err));
        setState('error');
      });
  }, [token]);

  // If this browser is logged in, update the profile so the reminder banner disappears.
  useEffect(() => {
    if (state === 'done' && authStatus === 'authenticated') refreshUser().catch(() => {});
  }, [state, authStatus, refreshUser]);

  const next = authStatus === 'authenticated' ? '/dashboard' : '/login';
  const nextLabel = authStatus === 'authenticated' ? 'Go to my files' : 'Log in';

  return (
    <AuthLayout
      title={
        state === 'working'
          ? 'Verifying your email…'
          : state === 'done'
            ? 'Email verified'
            : "We couldn't verify your email"
      }
    >
      <div className="space-y-5 text-sm text-slate-600">
        {state === 'working' && <Loader2 className="size-10 animate-spin text-blue-600" />}
        {state === 'done' && (
          <>
            <CircleCheck className="size-10 text-green-600" aria-hidden="true" />
            <p>Thanks – your email address is confirmed.</p>
          </>
        )}
        {state === 'error' && (
          <>
            <CircleAlert className="size-10 text-amber-500" aria-hidden="true" />
            <p>{error}</p>
            <p>Log in and use “Resend email” in the reminder at the top of the page.</p>
          </>
        )}
        {state !== 'working' && (
          <Link
            to={next}
            className="inline-flex w-full justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {nextLabel}
          </Link>
        )}
      </div>
    </AuthLayout>
  );
}
