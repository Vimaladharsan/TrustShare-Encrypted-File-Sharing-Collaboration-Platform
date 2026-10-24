import { CheckCircle2, KeyRound, Mail, UserRound } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { updateProfile } from '../../api/account';
import { getErrorMessage } from '../../api/client';
import { useAuth } from '../../auth/useAuth';
import { formatDate, timeAgo } from '../../utils/format';
import Button from '../Button';
import FormField from '../FormField';
import SettingsCard from './SettingsCard';

/** Profile tab: edit the display name, see account details and what the role allows. */
export default function ProfileTab() {
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState(user.full_name);
  const [saving, setSaving] = useState(false);
  const cleaned = name.trim().replace(/\s+/g, ' ');
  const changed = cleaned !== user.full_name;
  const valid = cleaned.length >= 2 && cleaned.length <= 100;

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await updateProfile(cleaned);
      await refreshUser();
      setName(cleaned);
      toast.success('Your name was updated.');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <SettingsCard
        title="Personal information"
        description="Your name is shown to people you share files with."
      >
        <form
          onSubmit={handleSubmit}
          className="flex max-w-xl flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="flex-1">
            <FormField
              label="Display name"
              icon={UserRound}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              autoComplete="name"
              hint={!valid ? 'Use 2 to 100 characters.' : undefined}
            />
          </div>
          <Button type="submit" loading={saving} disabled={!changed || !valid}>
            Save
          </Button>
        </form>
      </SettingsCard>

      <SettingsCard title="Account details">
        <dl className="grid gap-x-6 gap-y-5 text-sm sm:grid-cols-2">
          <Detail icon={Mail} label="Email">
            <span className="flex flex-wrap items-center gap-2">
              {user.email}
              {user.is_email_verified ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-600/15 ring-inset">
                  <CheckCircle2 className="size-3" aria-hidden="true" /> Verified
                </span>
              ) : (
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-amber-600/15 ring-inset">
                  Not verified
                </span>
              )}
            </span>
          </Detail>
          <Detail icon={KeyRound} label="Sign-in method">
            {user.has_password ? 'Email and password' : 'Google account (no password)'}
            {user.mfa_enabled && ' + two-step code'}
          </Detail>
          <Detail label="Member since">{formatDate(user.created_at)}</Detail>
          <Detail label="Last sign-in">
            {user.last_login_at ? timeAgo(user.last_login_at) : '—'}
          </Detail>
        </dl>
      </SettingsCard>

      <SettingsCard
        title="What your role allows"
        description="Permissions are checked by the server on every request."
      >
        <ul className="flex flex-wrap gap-2">
          {user.permissions.map((permission) => (
            <li
              key={permission}
              className="rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-xs text-slate-700 ring-1 ring-slate-200 ring-inset"
            >
              {permission}
            </li>
          ))}
        </ul>
      </SettingsCard>
    </div>
  );
}

function Detail({ icon: Icon, label, children }) {
  return (
    <div>
      <dt className="flex items-center gap-1.5 text-slate-500">
        {Icon && <Icon className="size-3.5" aria-hidden="true" />}
        {label}
      </dt>
      <dd className="mt-1 font-medium text-slate-900">{children}</dd>
    </div>
  );
}
