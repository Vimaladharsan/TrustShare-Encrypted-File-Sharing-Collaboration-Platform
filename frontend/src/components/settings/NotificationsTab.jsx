import { Bell, Mail } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { getErrorMessage } from '../../api/client';
import { getPreferences, updatePreferences } from '../../api/notifications';
import { ErrorState, Loading } from '../StateMessage';
import SettingsCard from './SettingsCard';

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
              <button
                type="button"
                role="switch"
                aria-checked={item.email}
                aria-label={`Email for ${item.label}`}
                disabled={saving === item.type}
                onClick={() => toggle(item)}
                className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition disabled:opacity-60 ${
                  item.email ? 'bg-blue-600' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`inline-block size-5 rounded-full bg-white shadow transition ${
                    item.email ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            )}
          </li>
        ))}
      </ul>
    </SettingsCard>
  );
}
