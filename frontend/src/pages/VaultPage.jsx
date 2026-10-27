import {
  Download,
  Eye,
  FolderOutput,
  KeyRound,
  Lock,
  LockKeyhole,
  Pencil,
  RotateCcw,
  ShieldCheck,
  Trash2,
  Upload,
  Vault,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router';
import { toast } from 'sonner';

import { getErrorMessage } from '../api/client';
import {
  changeVaultPassword,
  createVault,
  deleteVaultFile,
  downloadVaultFile,
  getVaultStatus,
  listVaultFiles,
  moveOutOfVault,
  previewVaultFile,
  renameVaultFile,
  resetVault,
  uploadToVault,
} from '../api/vault';
import { useAuth } from '../auth/useAuth';
import Button from '../components/Button';
import FilePreviewDialog from '../components/files/FilePreviewDialog';
import FileTable from '../components/files/FileTable';
import FormField from '../components/FormField';
import Modal from '../components/Modal';
import { Empty, ErrorState, Loading } from '../components/StateMessage';
import VaultPasswordDialog from '../components/vault/VaultPasswordDialog';
import { formatBytes } from '../utils/format';

const MIN_LENGTH = 8;

/**
 * Secure vault: files sealed with a key made from the vault password. The password is asked for
 * every action and never kept – leaving the page (or "Lock") forgets the list too.
 */
export default function VaultPage() {
  const { refreshUsage } = useOutletContext();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const [files, setFiles] = useState(null); // null = locked
  const [dialog, setDialog] = useState(null);
  const uploadInput = useRef(null);

  const loadStatus = useCallback(() => {
    setError('');
    getVaultStatus()
      .then(setStatus)
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  useEffect(loadStatus, [loadStatus]);

  /** After an action: show the fresh list (with the password just entered) and update meters. */
  async function refresh(password) {
    setFiles(await listVaultFiles(password));
    loadStatus();
    refreshUsage();
  }

  function lock() {
    setFiles(null);
    setDialog(null);
    toast.success('Vault locked');
  }

  if (error) return <ErrorState message={error} onRetry={loadStatus} />;
  if (!status) return <Loading />;
  if (!status.available) {
    return (
      <Empty
        icon={Vault}
        title="No vault for this account"
        text="Guest accounts are read-only, so they can't store files in a vault."
      />
    );
  }

  const fileActions = (file) => [
    file.can_preview && {
      label: 'Preview',
      icon: Eye,
      onClick: () => setDialog({ type: 'preview', file }),
    },
    { label: 'Download', icon: Download, onClick: () => setDialog({ type: 'download', file }) },
    { label: 'Rename', icon: Pencil, onClick: () => setDialog({ type: 'rename', file }) },
    {
      label: 'Move to My Files',
      icon: FolderOutput,
      onClick: () => setDialog({ type: 'moveOut', file }),
    },
    {
      label: 'Delete forever',
      icon: Trash2,
      danger: true,
      onClick: () => setDialog({ type: 'delete', file }),
    },
  ];

  return (
    <div className="space-y-5">
      <VaultHeader status={status} unlocked={files !== null}>
        {files !== null && (
          <>
            <Button variant="secondary" onClick={() => setDialog({ type: 'settings' })}>
              <KeyRound className="size-4" aria-hidden="true" /> Vault settings
            </Button>
            <Button variant="secondary" onClick={lock}>
              <Lock className="size-4" aria-hidden="true" /> Lock
            </Button>
            <Button onClick={() => uploadInput.current?.click()}>
              <Upload className="size-4" aria-hidden="true" /> Add files
            </Button>
          </>
        )}
      </VaultHeader>

      <input
        ref={uploadInput}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          const chosen = [...e.target.files];
          e.target.value = '';
          if (chosen.length) setDialog({ type: 'upload', chosen });
        }}
      />

      {!status.exists && <SetupCard onCreated={loadStatus} />}
      {status.exists && files === null && (
        <UnlockCard
          lockedMinutes={status.locked_minutes}
          onUnlocked={setFiles}
          onFailed={loadStatus}
          onForgot={() => setDialog({ type: 'reset' })}
        />
      )}
      {files !== null &&
        (files.length === 0 ? (
          <Empty
            icon={LockKeyhole}
            title="Your vault is empty"
            text="Add files here, or use “Move to vault” on any file in My Files."
          />
        ) : (
          <FileTable
            files={files}
            actionsFor={fileActions}
            onOpen={(file) => file.can_preview && setDialog({ type: 'preview', file })}
          />
        ))}

      {/* ---------- dialogs: each vault action asks for the password ---------- */}
      {dialog?.type === 'preview' && !dialog.blob && (
        <VaultPasswordDialog
          title={`Open “${dialog.file.name}”`}
          confirmLabel="Open"
          onConfirm={async (password) => {
            // Decrypted once, kept only in memory while the preview is open.
            const blob = await previewVaultFile(dialog.file.id, password);
            setDialog({ ...dialog, blob });
          }}
          onClose={() => setDialog((d) => (d?.blob ? d : null))}
        />
      )}
      {dialog?.type === 'preview' && dialog.blob && (
        <FilePreviewDialog
          file={dialog.file}
          load={() => Promise.resolve(dialog.blob)}
          onDownload={() => setDialog({ type: 'download', file: dialog.file })}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'download' && (
        <VaultPasswordDialog
          title={`Download “${dialog.file.name}”`}
          confirmLabel="Download"
          onConfirm={(password) => downloadVaultFile(dialog.file, password)}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'rename' && (
        <VaultPasswordDialog
          title="Rename file"
          nameField={{ label: 'File name', initialValue: dialog.file.name }}
          confirmLabel="Rename"
          onConfirm={async (password, name) => {
            await renameVaultFile(dialog.file.id, name, password);
            await refresh(password);
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'moveOut' && (
        <VaultPasswordDialog
          title="Move to My Files"
          description={`“${dialog.file.name}” leaves the vault and becomes a normal file in My Files (top level). It will no longer need the vault password.`}
          confirmLabel="Move out"
          onConfirm={async (password) => {
            await moveOutOfVault(dialog.file.id, password);
            await refresh(password);
            toast.success('Moved to My Files');
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'delete' && (
        <VaultPasswordDialog
          title="Delete forever?"
          description={`“${dialog.file.name}” and its encryption key are destroyed. The vault has no trash – this can't be undone.`}
          confirmLabel="Delete forever"
          danger
          onConfirm={async (password) => {
            await deleteVaultFile(dialog.file.id, password);
            await refresh(password);
            toast.success('File deleted');
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'upload' && (
        <VaultPasswordDialog
          title={`Add ${dialog.chosen.length} file${dialog.chosen.length === 1 ? '' : 's'} to the vault`}
          description={dialog.chosen.map((f) => f.name).join(', ')}
          confirmLabel="Encrypt & add"
          onConfirm={async (password) => {
            const failed = [];
            for (const file of dialog.chosen) {
              try {
                await uploadToVault(file, password);
              } catch (err) {
                if (err.response?.status === 403 || err.response?.status === 429) throw err;
                failed.push(`${file.name}: ${getErrorMessage(err)}`);
              }
            }
            await refresh(password);
            const added = dialog.chosen.length - failed.length;
            if (added) toast.success(`${added} file${added === 1 ? '' : 's'} added to the vault`);
            failed.forEach((message) => toast.error(message));
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.type === 'settings' && (
        <ChangePasswordDialog onClose={() => setDialog(null)} onChanged={lock} />
      )}
      {dialog?.type === 'reset' && (
        <ResetDialog
          onClose={() => setDialog(null)}
          onReset={() => {
            setFiles(null);
            loadStatus();
            refreshUsage();
          }}
        />
      )}
    </div>
  );
}

function VaultHeader({ status, unlocked, children }) {
  return (
    <section className="shadow-card relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950 p-6 text-white">
      <div className="pointer-events-none absolute -top-20 -right-10 size-64 rounded-full bg-indigo-500/20 blur-3xl" />
      <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <span
            className={`grid size-12 shrink-0 place-items-center rounded-2xl ring-1 ${
              unlocked
                ? 'bg-amber-400/15 text-amber-300 ring-amber-300/30'
                : 'bg-emerald-400/15 text-emerald-300 ring-emerald-300/30'
            }`}
          >
            {unlocked ? (
              <Vault className="size-6" aria-hidden="true" />
            ) : (
              <LockKeyhole className="size-6" aria-hidden="true" />
            )}
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Secure vault</h1>
            <p className="text-sm text-slate-300">
              {status.exists
                ? `${status.file_count} file${status.file_count === 1 ? '' : 's'} · ${formatBytes(status.size_bytes)} · ${unlocked ? 'unlocked on this page' : 'locked'}`
                : 'A private place for your most sensitive files'}
            </p>
          </div>
        </div>
        {children && <div className="flex flex-wrap gap-2">{children}</div>}
      </div>
      <p className="relative mt-4 flex items-start gap-2 text-xs text-slate-400">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-300" aria-hidden="true" />
        Extra encryption: vault files and their names are sealed with a key made from your vault
        password. Without it nobody can open them – not even the server. Never shared, never in
        search or Recent.
      </p>
    </section>
  );
}

function SetupCard({ onCreated }) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [understood, setUnderstood] = useState(false);
  const [saving, setSaving] = useState(false);
  const matches = password === confirm;
  const valid = password.length >= MIN_LENGTH && matches && understood;

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await createVault(password);
      toast.success('Your vault is ready');
      onCreated();
    } catch (err) {
      toast.error(getErrorMessage(err));
      setSaving(false);
    }
  }

  return (
    <section className="card mx-auto max-w-lg p-6">
      <h2 className="text-lg font-semibold text-slate-950">Create your vault</h2>
      <p className="mt-1 text-sm text-slate-600">
        Choose a vault password that is <strong>different from your login password</strong>.
        You&apos;ll enter it every time you open, add or change a vault file.
      </p>
      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        <FormField
          label="Vault password"
          icon={KeyRound}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          hint={
            password && password.length < MIN_LENGTH
              ? `At least ${MIN_LENGTH} characters`
              : undefined
          }
          required
        />
        <FormField
          label="Repeat vault password"
          icon={KeyRound}
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          hint={confirm && !matches ? 'Passwords do not match' : undefined}
          required
        />
        <label className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
          <input
            type="checkbox"
            checked={understood}
            onChange={(e) => setUnderstood(e.target.checked)}
            className="mt-0.5 size-4 accent-amber-600"
          />
          I understand that if I forget my vault password, the files in it can&apos;t be recovered –
          the vault can only be reset (emptied).
        </label>
        <Button type="submit" loading={saving} disabled={!valid} className="w-full">
          <LockKeyhole className="size-4" aria-hidden="true" /> Create vault
        </Button>
      </form>
    </section>
  );
}

function UnlockCard({ lockedMinutes, onUnlocked, onFailed, onForgot }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setWorking(true);
    try {
      onUnlocked(await listVaultFiles(password));
    } catch (err) {
      setError(getErrorMessage(err));
      onFailed();
    } finally {
      setPassword('');
      setWorking(false);
    }
  }

  return (
    <section className="card mx-auto max-w-md p-6 text-center">
      <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-indigo-50 text-indigo-600 ring-1 ring-indigo-100">
        <LockKeyhole className="size-7" aria-hidden="true" />
      </span>
      <h2 className="mt-4 text-lg font-semibold text-slate-950">Your vault is locked</h2>
      <p className="mt-1 text-sm text-slate-600">Enter your vault password to see your files.</p>
      {lockedMinutes > 0 ? (
        <p role="alert" className="mt-5 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          Too many wrong passwords – the vault is locked for {lockedMinutes} more minute
          {lockedMinutes === 1 ? '' : 's'}.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="mt-5 space-y-3 text-left">
          <FormField
            label="Vault password"
            icon={KeyRound}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="off"
            autoFocus
            required
          />
          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" loading={working} disabled={!password} className="w-full">
            Unlock
          </Button>
        </form>
      )}
      <button
        type="button"
        onClick={onForgot}
        className="mt-4 text-sm font-medium text-slate-500 hover:text-slate-800"
      >
        Forgot your vault password?
      </button>
    </section>
  );
}

function ChangePasswordDialog({ onClose, onChanged }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);
  const valid = current && next.length >= MIN_LENGTH && next === confirm;

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setWorking(true);
    try {
      await changeVaultPassword(current, next);
      toast.success('Vault password changed – use the new one from now on');
      onClose();
      onChanged();
    } catch (err) {
      setError(getErrorMessage(err));
      setWorking(false);
    }
  }

  return (
    <Modal title="Change vault password" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-slate-600">
          Every file key in your vault is re-locked with the new password. The files themselves
          aren&apos;t re-uploaded.
        </p>
        <FormField
          label="Current vault password"
          icon={KeyRound}
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="off"
          required
        />
        <FormField
          label="New vault password"
          icon={KeyRound}
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
          hint={next && next.length < MIN_LENGTH ? `At least ${MIN_LENGTH} characters` : undefined}
          required
        />
        <FormField
          label="Repeat new vault password"
          icon={KeyRound}
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          hint={confirm && next !== confirm ? 'Passwords do not match' : undefined}
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={working} disabled={!valid}>
            Change password
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ResetDialog({ onClose, onReset }) {
  const { user } = useAuth();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);
  const expected = user.has_password ? 'DELETE' : user.email;
  const valid =
    (!user.has_password || password) && confirm.trim().toLowerCase() === expected.toLowerCase();

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setWorking(true);
    try {
      const result = await resetVault({
        account_password: user.has_password ? password : null,
        confirm: confirm.trim(),
      });
      toast.success(`Vault reset – ${result.files_deleted} file(s) deleted`);
      onClose();
      onReset();
    } catch (err) {
      setError(getErrorMessage(err));
      setWorking(false);
    }
  }

  return (
    <Modal title="Reset your vault?" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
          <RotateCcw className="mr-1 inline size-4" aria-hidden="true" />
          Without the vault password the files can&apos;t be decrypted by anyone. Resetting{' '}
          <strong>deletes every file in the vault</strong> so you can start a new one.
        </p>
        {user.has_password && (
          <FormField
            label="Your account (login) password"
            icon={KeyRound}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        )}
        <FormField
          label={`Type ${expected} to confirm`}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="off"
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="danger" loading={working} disabled={!valid}>
            Delete vault
          </Button>
        </div>
      </form>
    </Modal>
  );
}
