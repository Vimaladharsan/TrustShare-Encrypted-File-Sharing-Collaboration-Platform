import { FileCheck2, History, KeyRound, LockKeyhole, UsersRound } from 'lucide-react';

import { Link } from 'react-router';

import { fileIcon } from '../utils/format';
import Logo from './Logo';

// Only features that work today – encryption and sharing are added in Milestone 2.
const FEATURES = [
  { icon: FileCheck2, title: 'Verified uploads', text: 'File types checked by content, not name' },
  { icon: UsersRound, title: 'Role-based access', text: 'Admin, User and Guest permissions' },
  { icon: KeyRound, title: 'Two-step verification', text: 'Authenticator codes and backup codes' },
  { icon: History, title: 'Activity log', text: 'Every upload and change is recorded' },
];

/**
 * Login, register and MFA screens: brand panel on the left (large screens only), form on the right.
 */
export default function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <main className="flex min-h-screen bg-slate-50 lg:p-4">
      <Showcase />
      <section className="flex flex-1 items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-10 inline-block lg:hidden" aria-label="TrustShare home">
            <Logo />
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{title}</h1>
          {subtitle && <p className="mt-2 text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <p className="mt-8 text-center text-sm text-slate-500">{footer}</p>}
        </div>
      </section>
    </main>
  );
}

function Showcase() {
  return (
    <aside className="relative hidden w-[46%] max-w-2xl flex-col justify-between overflow-hidden rounded-3xl bg-slate-950 p-10 text-white lg:flex xl:p-12">
      {/* soft glow + dot grid in the background */}
      <div className="pointer-events-none absolute -top-32 -right-32 size-96 rounded-full bg-blue-600/30 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -left-24 size-96 rounded-full bg-indigo-500/20 blur-3xl" />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage: 'radial-gradient(white 1px, transparent 1px)',
          backgroundSize: '22px 22px',
        }}
      />

      <Link to="/" className="relative w-fit" aria-label="TrustShare home">
        <Logo variant="light" />
      </Link>

      <div className="relative">
        <h2 className="text-4xl leading-tight font-semibold tracking-tight xl:text-5xl">
          Your files.
          <br />
          Your rules.
          <br />
          <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
            Nothing left to chance.
          </span>
        </h2>
        <p className="mt-4 max-w-md text-slate-300">
          A private workspace for your documents – every upload verified, every action recorded, and
          access controlled by role.
        </p>
        <FilesPreview />
      </div>

      <ul className="relative grid grid-cols-2 gap-x-6 gap-y-5">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <li key={title} className="flex gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10 text-blue-300 ring-1 ring-white/10">
              <Icon className="size-4" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-sm font-medium">{title}</span>
              <span className="block text-xs text-slate-400">{text}</span>
            </span>
          </li>
        ))}
      </ul>
    </aside>
  );
}

const SAMPLE_FILES = [
  { name: 'Q4 report.pdf', size: '2.4 MB', category: 'document' },
  { name: 'Budget.xlsx', size: '820 KB', category: 'spreadsheet' },
  { name: 'Team photo.png', size: '3.1 MB', category: 'image' },
];

/** Decorative mini file list, drawn with HTML so it stays sharp and needs no image files. */
function FilesPreview() {
  return (
    <div className="relative mt-10 max-w-md" aria-hidden="true">
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-2xl backdrop-blur">
        <div className="mb-3 flex items-center justify-between pr-10">
          <span className="text-sm font-medium text-slate-200">Recent files</span>
          <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
            All checks passed
          </span>
        </div>
        <ul className="space-y-2">
          {SAMPLE_FILES.map((file) => {
            const { Icon, color } = fileIcon(file.category);
            return (
              <li
                key={file.name}
                className="flex items-center gap-3 rounded-lg bg-white/5 px-3 py-2 text-sm"
              >
                <Icon className={`size-4 ${color}`} />
                <span className="flex-1 truncate text-slate-200">{file.name}</span>
                <span className="text-xs text-slate-400">{file.size}</span>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="absolute -top-5 -right-5 grid size-14 place-items-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg ring-4 ring-slate-950">
        <LockKeyhole className="size-6 text-white" />
      </div>
    </div>
  );
}
