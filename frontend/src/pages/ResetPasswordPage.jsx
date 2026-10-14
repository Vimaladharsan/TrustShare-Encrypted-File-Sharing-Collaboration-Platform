import { Lock } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { toast } from 'sonner';

import { resetPassword } from '../api/auth';
import { getErrorCode, getErrorMessage } from '../api/client';
import AuthLayout from '../components/AuthLayout';
import Button from '../components/Button';
import FormField from '../components/FormField';
import PasswordChecklist from '../components/PasswordChecklist';
import { passwordMeetsRules } from '../utils/passwordRules';

/** Step 2: the page the emailed link opens (/reset-password?token=...). */
export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [linkInvalid, setLinkInvalid] = useState(!token);
  const [submitting, setSubmitting] = useState(false);

  const matches = password === confirm;
  const canSubmit = passwordMeetsRules(password) && matches;

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await resetPassword(token, password);
      toast.success('Password changed. Please log in with your new password.');
      navigate('/login', { replace: true });
    } catch (err) {
      if (getErrorCode(err) === 'INVALID_RESET_LINK') setLinkInvalid(true);
      else setError(getErrorMessage(err));
      setSubmitting(false);
    }
  }

  if (linkInvalid) {
    return (
      <AuthLayout
        title="This link has expired"
        subtitle="Reset links work once and only for 15 minutes."
      >
        <Link
          to="/forgot-password"
          className="inline-flex w-full justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Send a new link
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Choose a new password" subtitle="You'll be logged out on all other devices.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <FormField
            label="New password"
            icon={Lock}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            autoFocus
            required
          />
          <PasswordChecklist password={password} />
        </div>
        <FormField
          label="Confirm new password"
          icon={Lock}
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          hint={confirm && !matches ? 'Passwords do not match' : undefined}
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <Button type="submit" loading={submitting} disabled={!canSubmit} className="w-full">
          Change password
        </Button>
      </form>
    </AuthLayout>
  );
}
