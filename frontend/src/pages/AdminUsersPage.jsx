import { Lock, Search, ShieldCheck, ShieldOff, UsersRound } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { listUsers, unlockUser, updateUser } from '../api/admin';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../auth/useAuth';
import Button from '../components/Button';
import ConfirmDialog from '../components/ConfirmDialog';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import { formatDate } from '../utils/format';

const PAGE_SIZE = 20;
const ROLES = ['admin', 'user', 'guest'];

/** Admins only: every account with its role, status, MFA and lockout state. */
export default function AdminUsersPage() {
  const { user: me, can } = useAuth();
  const allowed = can('user:read');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState(''); // the search actually sent (after a short pause)
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [confirm, setConfirm] = useState(null);

  // Wait until typing pauses before searching, instead of one request per key press.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(() => {
    if (!allowed) return;
    setError('');
    listUsers({ search: query, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)));
  }, [allowed, query, page]);

  useEffect(load, [load]);

  // The page is only linked for admins, but someone could type the URL – the API would
  // refuse anyway (403); this just shows a clear message instead of an error.
  if (!allowed) {
    return (
      <Empty icon={ShieldOff} title="Admins only" text="You don't have access to this page." />
    );
  }

  const canManage = can('user:manage');

  async function apply(target, action, successMessage) {
    setBusyId(target.id);
    try {
      const updated = await action();
      setData((current) => ({
        ...current,
        items: current.items.map((u) => (u.id === updated.id ? updated : u)),
      }));
      toast.success(successMessage);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  function changeRole(target, role) {
    apply(target, () => updateUser(target.id, { role }), `${target.full_name} is now ${role}.`);
  }

  function setActive(target, isActive) {
    const run = () =>
      apply(
        target,
        () => updateUser(target.id, { is_active: isActive }),
        isActive ? `${target.full_name} can log in again.` : `${target.full_name} is disabled.`,
      );
    if (isActive) return run();
    setConfirm({
      title: 'Disable this account?',
      message: `${target.full_name} (${target.email}) will be logged out of every device and won't be able to log in until the account is enabled again.`,
      label: 'Disable',
      action: run,
    });
  }

  function unlock(target) {
    apply(target, () => unlockUser(target.id), `${target.full_name} is unlocked.`);
  }

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Users</h1>
          <p className="text-sm text-slate-500">
            Manage roles and access. {data && `${total} account${total === 1 ? '' : 's'}`}
          </p>
        </div>
        <label className="relative block sm:w-72">
          <span className="sr-only">Search users</span>
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name or email"
            className="w-full rounded-lg border border-slate-300 py-2 pr-3 pl-9 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-100 focus:outline-none"
          />
        </label>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <Loading />}
      {!error && data && data.items.length === 0 && (
        <Empty icon={UsersRound} title="No users found" text="Try a different search." />
      )}

      {!error && data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last login</th>
                <th className="px-4 py-3 font-medium">Joined</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((u) => {
                const isMe = u.id === me.id;
                const busy = busyId === u.id;
                return (
                  <tr key={u.id} className={u.is_active ? '' : 'bg-slate-50/70 text-slate-500'}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900">
                        {u.full_name}
                        {isMe && <span className="ml-2 text-xs text-slate-400">(you)</span>}
                      </p>
                      <p className="text-slate-500">{u.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => changeRole(u, e.target.value)}
                        disabled={!canManage || isMe || busy || !u.is_active}
                        aria-label={`Role of ${u.full_name}`}
                        title={isMe ? "You can't change your own role" : undefined}
                        className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm capitalize disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400"
                      >
                        {ROLES.map((role) => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        <Badge tone={u.is_active ? 'green' : 'slate'}>
                          {u.is_active ? 'Active' : 'Disabled'}
                        </Badge>
                        {!u.is_email_verified && <Badge tone="amber">Unverified</Badge>}
                        {u.mfa_enabled && (
                          <Badge tone="blue">
                            <ShieldCheck className="size-3" aria-hidden="true" /> 2-step
                          </Badge>
                        )}
                        {u.is_locked && (
                          <Badge tone="amber">
                            <Lock className="size-3" aria-hidden="true" /> Locked
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {u.last_login_at ? formatDate(u.last_login_at) : 'Never'}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3">
                      {canManage && !isMe && (
                        <div className="flex justify-end gap-2">
                          {u.is_locked && (
                            <Button variant="secondary" disabled={busy} onClick={() => unlock(u)}>
                              Unlock
                            </Button>
                          )}
                          <Button
                            variant="secondary"
                            disabled={busy}
                            onClick={() => setActive(u, !u.is_active)}
                          >
                            {u.is_active ? 'Disable' : 'Enable'}
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {data && pages > 1 && (
        <div className="flex items-center justify-end gap-3 text-sm text-slate-600">
          <span>
            Page {page + 1} of {pages}
          </span>
          <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>
            Previous
          </Button>
          <Button
            variant="secondary"
            disabled={page + 1 >= pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.label}
          onConfirm={confirm.action}
          onClose={() => setConfirm(null)}
        />
      )}
    </div>
  );
}

const TONES = {
  green: 'bg-green-50 text-green-700',
  slate: 'bg-slate-100 text-slate-600',
  blue: 'bg-blue-50 text-blue-700',
  amber: 'bg-amber-50 text-amber-700',
};

function Badge({ tone, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
