import { LogOut, Monitor, Smartphone } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';

import { getDevices, signOutDevice } from '../../api/account';
import { getErrorMessage } from '../../api/client';
import { useAuth } from '../../auth/useAuth';
import { formatDate, timeAgo } from '../../utils/format';
import Button from '../Button';
import ConfirmDialog from '../ConfirmDialog';
import { ErrorState, Loading } from '../StateMessage';
import SettingsCard from './SettingsCard';

/** Devices tab: every signed-in device, each can be signed out on its own. */
export default function DevicesTab() {
  const { logoutAll } = useAuth();
  const navigate = useNavigate();
  const [devices, setDevices] = useState(null);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState(null); // null | { device } | 'all'

  const load = useCallback(() => {
    setError('');
    getDevices()
      .then(setDevices)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  async function handleSignOut(device) {
    try {
      await signOutDevice(device.id);
      toast.success(`${device.browser} on ${device.os} was signed out.`);
      load();
    } catch (err) {
      toast.error(getErrorMessage(err));
      load();
    }
  }

  async function handleLogoutAll() {
    await logoutAll();
    toast.success('You have been logged out on every device.');
    navigate('/login');
  }

  return (
    <div className="space-y-6">
      <SettingsCard
        title="Signed-in devices"
        description="Don't recognise a device? Sign it out – it loses access immediately – and change your password."
      >
        {error && <ErrorState message={error} onRetry={load} />}
        {!error && !devices && <Loading rows={2} />}
        {!error && devices && (
          <ul className="-my-2 divide-y divide-slate-100">
            {devices.map((device) => {
              const Icon = device.kind === 'mobile' ? Smartphone : Monitor;
              return (
                <li key={device.id} className="flex flex-wrap items-center gap-4 py-4">
                  <span
                    className={`grid size-11 shrink-0 place-items-center rounded-xl ring-1 ring-inset ${
                      device.current
                        ? 'bg-blue-50 text-blue-600 ring-blue-100'
                        : 'bg-slate-50 text-slate-500 ring-slate-200'
                    }`}
                  >
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 font-medium text-slate-900">
                      {device.browser} on {device.os}
                      {device.current && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-600/15 ring-inset">
                          <span className="size-1.5 rounded-full bg-emerald-500" /> This device
                        </span>
                      )}
                    </p>
                    <p className="mt-0.5 text-sm text-slate-500">
                      <span className="font-mono text-xs">{device.ip_address}</span> ·{' '}
                      {device.location}
                    </p>
                    <p className="text-xs text-slate-400">
                      Signed in {formatDate(device.signed_in_at)} · active{' '}
                      {timeAgo(device.last_active_at)}
                    </p>
                  </div>
                  {!device.current && (
                    <Button variant="secondary" size="sm" onClick={() => setConfirm({ device })}>
                      Sign out
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </SettingsCard>

      <SettingsCard
        title="Sign out everywhere"
        description="Lost a device or used a shared computer? End every session of your account – including this one."
      >
        <Button variant="secondary" onClick={() => setConfirm('all')}>
          <LogOut className="size-4" aria-hidden="true" /> Log out of all devices
        </Button>
      </SettingsCard>

      {confirm === 'all' && (
        <ConfirmDialog
          title="Log out of all devices?"
          message="Every device signed in to your account – this one too – will need to log in again."
          confirmLabel="Log out everywhere"
          onConfirm={handleLogoutAll}
          onClose={() => setConfirm(null)}
        />
      )}
      {confirm?.device && (
        <ConfirmDialog
          title="Sign out this device?"
          message={`${confirm.device.browser} on ${confirm.device.os} (${confirm.device.ip_address}) will lose access immediately and must log in again.`}
          confirmLabel="Sign out device"
          onConfirm={() => handleSignOut(confirm.device)}
          onClose={() => setConfirm(null)}
        />
      )}
    </div>
  );
}
