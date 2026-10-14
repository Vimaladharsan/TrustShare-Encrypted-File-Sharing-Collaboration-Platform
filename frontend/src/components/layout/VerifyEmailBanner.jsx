import { MailWarning } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { resendVerification } from '../../api/auth';
import { getErrorMessage } from '../../api/client';
import { useAuth } from '../../auth/useAuth';

/** Reminder shown at the top of the dashboard until the user verifies their email. */
export default function VerifyEmailBanner() {
  const { user } = useAuth();
  const [sending, setSending] = useState(false);

  if (!user || user.is_email_verified) return null;

  async function handleResend() {
    setSending(true);
    try {
      toast.success(await resendVerification());
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <MailWarning className="size-4 shrink-0" aria-hidden="true" />
      <span>
        Please verify your email – we sent a link to <strong>{user.email}</strong>.
      </span>
      <button
        type="button"
        onClick={handleResend}
        disabled={sending}
        className="font-medium underline hover:no-underline disabled:opacity-50"
      >
        {sending ? 'Sending…' : 'Resend email'}
      </button>
    </div>
  );
}
