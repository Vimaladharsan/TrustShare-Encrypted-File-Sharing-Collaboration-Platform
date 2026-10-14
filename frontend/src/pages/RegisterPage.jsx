import { Lock, Mail, User } from 'lucide-react';
import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import { useAuth } from '../auth/useAuth';
import AuthLayout from '../components/AuthLayout';
import Button from '../components/Button';
import FormField from '../components/FormField';
import PasswordChecklist from '../components/PasswordChecklist';
import { passwordMeetsRules } from '../utils/passwordRules';

export default function RegisterPage() {
  const { status, register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authenticated') return <Navigate to="/files" replace />;

  const passwordOk = passwordMeetsRules(password);
  const matches = password === confirm;
  const canSubmit = fullName.trim().length >= 2 && email && passwordOk && matches;

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await register(fullName.trim(), email, password);
      toast.success(
        'Account created. We sent a verification link to your email – you can log in now.',
      );
      navigate('/login', { state: { email } });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Secure file sharing for your team"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-blue-600 hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField
          label="Full name"
          icon={User}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          autoComplete="name"
          required
        />
        <FormField
          label="Email"
          icon={Mail}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <div>
          <FormField
            label="Password"
            icon={Lock}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
          <PasswordChecklist password={password} />
        </div>
        <FormField
          label="Confirm password"
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
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}
