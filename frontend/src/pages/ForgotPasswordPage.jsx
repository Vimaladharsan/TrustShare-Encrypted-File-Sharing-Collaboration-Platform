import { Mail, MailCheck } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation } from 'react-router';

import { forgotPassword } from '../api/auth';
import { getErrorMessage } from '../api/client';
import AuthLayout from '../components/AuthLayout';
import Button from '../components/Button';
import FormField from '../components/FormField';

/** Step 1 of resetting a password: ask for the email and send the link. */
export default function ForgotPasswordPage() {
  const location = useLocation();
  const [email, setEmail] = useState(location.state?.email || '');
  const [sentTo, setSentTo] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await forgotPassword(email);
      setSentTo(email);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const backToLogin = (
    <Link to="/login" className="font-medium text-blue-600 hover:underline">
      ← Back to login
    </Link>
  );

  if (sentTo) {
    return (
      <AuthLayout title="Check your email" footer={backToLogin}>
        <div className="space-y-4 text-sm text-slate-600">
          <MailCheck className="size-10 text-blue-600" aria-hidden="true" />
          <p>
            If an account exists for <strong className="text-slate-900">{sentTo}</strong>, we've
            sent a link to reset the password. It works once and expires in 15 minutes.
          </p>
          <p>Didn't get it? Check your spam folder, or try again in a minute.</p>
          <Button variant="secondary" onClick={() => setSentTo('')}>
            Send another link
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Forgot your password?"
      subtitle="Enter your email and we'll send you a link to choose a new one."
      footer={backToLogin}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField
          label="Email"
          icon={Mail}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          placeholder="you@example.com"
          autoFocus
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <Button type="submit" loading={submitting} className="w-full">
          Send reset link
        </Button>
      </form>
    </AuthLayout>
  );
}
