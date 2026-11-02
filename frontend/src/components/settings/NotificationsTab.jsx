import { Bell, Mail, MonitorSmartphone } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { getPreferences, updatePreferences } from '../../api/notifications';
import {
  desktopEnabled,
  desktopPermission,
  disableDesktop,
  enableDesktop,
} from '../../notifications/desktop';
import { ErrorState, Loading } from '../StateMessage';
import SettingsCard from './SettingsCard';

/** On/off switch used on this page. */
function Switch({ on, label, disabled, onClick }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition disabled:opacity-60 ${
        on ? 'bg-blue-600' : 'bg-slate-300'
      }`}
    >
      <span
        className={`inline-block size-5 rounded-full bg-white shadow transition ${
          on ? 'translate-x-5' : 'translate-x-0.5'
        }`}
      />
    </button>
  );
}

/** Desktop pop-ups for this browser: asks for the browser's permission when turned on. */
function DesktopPopups() {
  const [on, setOn] = useState(desktopEnabled);
  const [permission, setPermission] = useState(desktopPermission);
  const [asking, setAsking] = useState(false);

  async function toggle() {
    if (on) {
      disableDesktop();
      setOn(false);
      toast.success('Desktop pop-ups off on this device');
      return;
    }
    setAsking(true);
    const result = await enableDesktop();
    setAsking(false);
    setPermission(desktopPermission());
    if (result === 'granted') {
      setOn(true);
      toast.success('Desktop pop-ups on – you will see them while TrustShare is in the background');
    } else if (result === 'denied') {
      toast.error('Your browser blocked notifications for TrustShare.');
    }
  }

  const note =
    permission === 'unsupported'
      ? "This browser can't show desktop notifications."
      : permission === 'denied'
        ? 'Blocked in this browser – allow notifications for this site in the browser’s site settings (padlock icon), then turn this on.'
        : 'Pop up on your desktop when something arrives while TrustShare is open in a background tab. Applies to this browser only.';

  return (
    <SettingsCard
      title="Desktop pop-ups"
      description="Get notified even when you're working in another tab or window."
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <MonitorSmartphone className="mt-0.5 size-5 shrink-0 text-slate-400" aria-hidden="true" />
          <div className="min-w-0">
            <p className="font-medium text-slate-900">
              Desktop pop-ups on this device{' '}
              <span
                className={`text-xs font-semibold ${on ? 'text-emerald-600' : 'text-slate-400'}`}
              >
                {on ? 'On' : 'Off'}
              </span>
            </p>
            <p className="mt-0.5 text-xs text-slate-500">{note}</p>
          </div>
        </div>
        <Switch
          on={on}
          label="Desktop pop-ups on this device"
          disabled={asking || permission === 'unsupported' || (permission === 'denied' && !on)}
          onClick={toggle}
        />
      </div>
    </SettingsCard>
  );
}

/** Settings → Notifications: every notification appears in the app; email is per type. */
export default function NotificationsTab() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState('');

  const load = useCallback(() => {
    setError('');
    getPreferences()
      .then(setItems)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  async function toggle(item) {
    setSaving(item.type);
    try {
      setItems(await updatePreferences({ [item.type]: !item.email }));
      toast.success(`Email ${item.email ? 'off' : 'on'}: ${item.label.toLowerCase()}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving('');
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!items) return <Loading rows={3} />;
  return (
    <div className="space-y-6">
      <DesktopPopups />
      <SettingsCard
        title="Notifications"
        description="Everything shows up instantly under the bell. Choose what should also arrive by email."
      >
        <ul className="divide-y divide-slate-100">
          {items.map((item) => (
            <li key={item.type} className="flex items-center justify-between gap-4 py-3">
              <div className="min-w-0">
                <p className="font-medium text-slate-900">{item.label}</p>
                <p className="mt-0.5 flex items-center gap-3 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1">
                    <Bell className="size-3.5" aria-hidden="true" /> In the app
                  </span>
                  {item.email_optional ? (
                    <span className="inline-flex items-center gap-1">
                      <Mail className="size-3.5" aria-hidden="true" />
                      {item.email ? 'and by email' : 'no email'}
                    </span>
                  ) : (
                    <span>in the app only</span>
                  )}
                </p>
              </div>
              {item.email_optional && (
                <Switch
                  on={item.email}
                  label={`Email for ${item.label}`}
                  disabled={saving === item.type}
                  onClick={() => toggle(item)}
                />
              )}
            </li>
          ))}
        </ul>
      </SettingsCard>
    </div>
  );
}
