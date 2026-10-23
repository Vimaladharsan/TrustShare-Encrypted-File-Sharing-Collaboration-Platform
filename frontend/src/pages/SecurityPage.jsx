import {
  Activity,
  BadgeCheck,
  Download,
  FileLock2,
  KeyRound,
  Link2,
  Lock,
  RefreshCw,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';

// What actually protects the user's files – each card describes a feature that is built and
// running (see docs/architecture.md and docs/key-management.md), not a promise.
const FEATURES = [
  {
    icon: FileLock2,
    title: 'AES-256 encryption',
    text: 'Every file is encrypted with its own AES-256-GCM key before it is stored. The storage only ever holds unreadable data.',
  },
  {
    icon: Lock,
    title: 'HTTPS / TLS',
    text: 'Traffic is encrypted with TLS through a reverse proxy (locally https://localhost:8443), so nothing can be read or changed on the way.',
  },
  {
    icon: KeyRound,
    title: 'JWT authentication',
    text: 'Short-lived signed access tokens (15 minutes) kept only in memory, renewed with a rotating, HttpOnly refresh token.',
  },
  {
    icon: UserCheck,
    title: 'Google sign-in (OAuth 2.0)',
    text: 'Sign in with Google using the OAuth 2.0 / OpenID Connect standard with PKCE. Two-step verification still applies.',
  },
  {
    icon: ShieldCheck,
    title: 'Role-based access control',
    text: 'Every request is checked against your role’s permissions on the server. Not even admins can open your files.',
  },
  {
    icon: Link2,
    title: 'Temporary share links',
    text: 'Links always expire, can be view-only, can have a download limit and can be revoked instantly.',
  },
  {
    icon: Download,
    title: 'Download tracking',
    text: 'Every download of your files – by you, by people you shared with, or through a link – is recorded.',
  },
  {
    icon: Activity,
    title: 'Audit logging',
    text: 'Sign-ins, file actions and shares are written to an append-only activity log you can review.',
  },
  {
    icon: BadgeCheck,
    title: 'Secure token generation',
    text: 'Links, sessions and reset codes use 256-bit random values from the operating system; only their hashes are stored.',
  },
  {
    icon: RefreshCw,
    title: 'Key rotation',
    text: 'Master keys are versioned and can be rotated: every file key is re-protected with the new key without re-uploading.',
  },
];

/** How TrustShare protects your files and account (mentor's "Security" section). */
export default function SecurityPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Security</h1>
        <p className="text-sm text-slate-500">
          Your files and account are protected by these measures.
        </p>
      </div>
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <li key={title} className="flex flex-col rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <span className="flex size-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <Icon className="size-5" aria-hidden="true" />
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                <span className="size-1.5 rounded-full bg-green-600" aria-hidden="true" />
                Active
              </span>
            </div>
            <h2 className="mt-3 font-semibold text-slate-900">{title}</h2>
            <p className="mt-1 text-sm text-slate-600">{text}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
