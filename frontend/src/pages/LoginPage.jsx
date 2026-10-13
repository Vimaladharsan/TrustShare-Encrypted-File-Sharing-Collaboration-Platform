import { Hash, Lock, Mail, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router';

import { getErrorMessage } from '../api/client';
import { useAuth } from '../auth/useAuth';
import AuthLayout from '../components/AuthLayout';
import Button from '../components/Button';
import FormField from '../components/FormField';

export default function LoginPage() {
  const { status, login, completeMfa } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const goTo = location.state?.from || '/files';

  const [email, setEmail] = useState(location.state?.email || '');
  const [password, setPassword] = useState('');
  const [challenge, setChallenge] = useState(null); // set when MFA is required
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authenticated') return <Navigate to={goTo} replace />;

  async function handleLogin(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const data = await login(email, password);
      if (data.mfa_required) {
        setChallenge(data.challenge_id);
      } else {
        navigate(goTo, { replace: true });
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCode(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await completeMfa(challenge, code.trim());
      navigate(goTo, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
      setCode('');
      if (err.response?.data?.error?.code === 'MFA_CHALLENGE_EXPIRED') setChallenge(null);
    } finally {
      setSubmitting(false);
    }
  }

  // ---------- step 2: authenticator code ----------
  if (challenge) {
    return (
      <AuthLayout
        title="Two-step verification"
        subtitle="Enter the 6-digit code from your authenticator app, or a backup code."
      >
        <form onSubmit={handleCode} className="space-y-4">
          <div className="flex justify-center text-blue-600">
            <ShieldCheck className="size-10" aria-hidden="true" />
          </div>
          <FormField
            label="Verification code"
            icon={Hash}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="123456"
            autoFocus
            required
          />
          {error && <ErrorBox message={error} />}
          <Button type="submit" loading={submitting} className="w-full">
            Verify
          </Button>
          <button
            type="button"
            onClick={() => setChallenge(null)}
            className="w-full text-center text-sm text-slate-500 hover:text-slate-700"
          >
            ← Back to login
          </button>
        </form>
      </AuthLayout>
    );
  }

  // ---------- step 1: email + password ----------
  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Log in to your secure workspace"
      footer={
        <>
          New here?{' '}
          <Link to="/register" className="font-medium text-blue-600 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleLogin} className="space-y-4">
        <FormField
          label="Email"
          icon={Mail}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          placeholder="you@example.com"
          required
        />
        <FormField
          label="Password"
          icon={Lock}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        {error && <ErrorBox message={error} />}
        <Button type="submit" loading={submitting} className="w-full">
          Log in
        </Button>
      </form>
    </AuthLayout>
  );
}

function ErrorBox({ message }) {
  return (
    <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </p>
  );
}
