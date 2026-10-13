import {
  ArrowRight,
  Check,
  FileCheck2,
  FolderTree,
  History,
  KeyRound,
  Link2,
  LockKeyhole,
  ShieldCheck,
  UploadCloud,
  UserPlus,
  UsersRound,
} from 'lucide-react';
import { Link } from 'react-router';

import { useAuth } from '../auth/useAuth';
import ProductPreview from '../components/landing/ProductPreview';
import Logo from '../components/Logo';

const GITHUB_URL =
  'https://github.com/Vimaladharsan/TrustShare-Encrypted-File-Sharing-Collaboration-Platform';

// Real numbers from the system's design – no invented user counts.
const FACTS = [
  { value: 'SHA-256', label: 'fingerprint on every upload' },
  { value: '15 min', label: 'access token lifetime' },
  { value: '3 roles', label: 'built from 10 permissions' },
  { value: '25 MB', label: 'per file, checked by content' },
];

const FEATURES = [
  {
    icon: FileCheck2,
    title: 'Verified uploads',
    text: 'Every file is checked by its content, not its name – a program renamed to .pdf is rejected.',
    tone: 'bg-emerald-50 text-emerald-600',
  },
  {
    icon: FolderTree,
    title: 'Folders, search and trash',
    text: 'Nested folders with breadcrumbs, search across everything, filters, and a trash you can undo.',
    tone: 'bg-blue-50 text-blue-600',
  },
  {
    icon: UsersRound,
    title: 'Role-based access',
    text: 'Admin, User and Guest roles built from fine-grained permissions, enforced on every request.',
    tone: 'bg-violet-50 text-violet-600',
  },
  {
    icon: KeyRound,
    title: 'Two-step verification',
    text: 'Protect your account with codes from Google Authenticator, plus one-time backup codes.',
    tone: 'bg-amber-50 text-amber-600',
  },
  {
    icon: History,
    title: 'Activity log',
    text: 'Uploads, changes and rejected files are recorded with time, IP address and device.',
    tone: 'bg-rose-50 text-rose-600',
  },
  {
    icon: Link2,
    title: 'Encrypted storage and secure links',
    text: 'AES-256-GCM encryption with a unique key per file, and share links that expire.',
    tone: 'bg-cyan-50 text-cyan-600',
    soon: true,
  },
];

const STEPS = [
  {
    icon: UserPlus,
    title: 'Create your account',
    text: 'Sign up in seconds, then turn on two-step verification in Settings.',
  },
  {
    icon: UploadCloud,
    title: 'Upload your files',
    text: 'Drag and drop. Type, size and content are checked before anything is stored.',
  },
  {
    icon: FolderTree,
    title: 'Organise and control',
    text: 'Sort files into folders, find them instantly, and decide who can do what.',
  },
];

const SECURITY = [
  'Passwords hashed with bcrypt – never stored or logged',
  'Short-lived tokens with rotating, revocable sessions',
  'Account lockout and rate limiting against guessing',
  'Files stored under random names, never your filename',
  'Other users’ files are invisible – not just locked',
  'Every important action written to an audit log',
];

/** Public home page at "/". Logged-in visitors get a shortcut to their files. */
export default function LandingPage() {
  const { status } = useAuth();
  const loggedIn = status === 'authenticated';

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header loggedIn={loggedIn} />

      {/* ---------- hero ---------- */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[38rem] bg-gradient-to-b from-blue-50/80 to-white" />
        <div className="mx-auto grid max-w-6xl items-center gap-16 px-4 pt-16 pb-20 sm:px-6 lg:grid-cols-2 lg:pt-24">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-white px-3 py-1 text-xs font-medium text-blue-700">
              <LockKeyhole className="size-3.5" aria-hidden="true" />
              Private · Verified · Accountable
            </span>
            <h1 className="mt-6 text-4xl leading-tight font-semibold tracking-tight text-slate-900 sm:text-5xl lg:text-[3.4rem]">
              Share files with confidence.{' '}
              <span className="bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
                Stay in control of every one.
              </span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-slate-600">
              TrustShare is a secure workspace for your documents. Every upload is verified, every
              action is recorded, and every person only sees what their role allows.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to={loggedIn ? '/files' : '/register'}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 font-medium text-white shadow-lg shadow-blue-600/20 hover:bg-blue-700"
              >
                {loggedIn ? 'Open my files' : 'Get started – it’s free'}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              {!loggedIn && (
                <Link
                  to="/login"
                  className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-5 py-3 font-medium text-slate-700 hover:bg-slate-50"
                >
                  Log in
                </Link>
              )}
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
              {['Content-verified uploads', 'Role-based access', 'Two-step verification'].map(
                (item) => (
                  <li key={item} className="flex items-center gap-2">
                    <Check className="size-4 text-blue-600" aria-hidden="true" />
                    {item}
                  </li>
                ),
              )}
            </ul>
          </div>
          <ProductPreview />
        </div>
      </section>

      {/* ---------- facts ---------- */}
      <section className="border-y border-slate-100 bg-slate-50/60">
        <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-8 px-4 py-10 sm:px-6 lg:grid-cols-4">
          {FACTS.map((fact) => (
            <div key={fact.label}>
              <dt className="text-2xl font-semibold text-slate-900">{fact.value}</dt>
              <dd className="mt-1 text-sm text-slate-500">{fact.label}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* ---------- features ---------- */}
      <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
        <SectionTitle
          eyebrow="Features"
          title="Everything your files need, nothing they don’t"
          text="A familiar, Drive-like workspace with security built into every step."
        />
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text, tone, soon }) => (
            <article
              key={title}
              className="rounded-2xl border border-slate-200 p-6 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/60"
            >
              <div className="flex items-center justify-between">
                <span className={`grid size-11 place-items-center rounded-xl ${tone}`}>
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                {soon && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                    Milestone 2
                  </span>
                )}
              </div>
              <h3 className="mt-5 font-semibold text-slate-900">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{text}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ---------- how it works ---------- */}
      <section id="how-it-works" className="scroll-mt-20 bg-slate-50/60 py-24">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <SectionTitle
            eyebrow="How it works"
            title="Up and running in three steps"
            text="No setup, no installs – just your browser."
          />
          <ol className="mt-14 grid gap-8 md:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, text }, index) => (
              <li key={title} className="relative rounded-2xl bg-white p-6 ring-1 ring-slate-200">
                <span className="absolute top-6 right-6 text-4xl font-semibold text-slate-100">
                  {index + 1}
                </span>
                <span className="grid size-11 place-items-center rounded-xl bg-blue-600 text-white">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <h3 className="mt-5 font-semibold text-slate-900">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ---------- security ---------- */}
      <section id="security" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
        <div className="relative overflow-hidden rounded-3xl bg-slate-950 px-6 py-14 text-white sm:px-12">
          <div className="pointer-events-none absolute -top-24 -right-24 size-80 rounded-full bg-blue-600/30 blur-3xl" />
          <div className="relative grid gap-12 lg:grid-cols-2 lg:items-center">
            <div>
              <span className="grid size-12 place-items-center rounded-xl bg-white/10 text-blue-300 ring-1 ring-white/10">
                <ShieldCheck className="size-6" aria-hidden="true" />
              </span>
              <h2 className="mt-6 text-3xl font-semibold tracking-tight">
                Security isn’t a feature here. It’s the foundation.
              </h2>
              <p className="mt-4 text-slate-300">
                The backend checks identity and permission on every single request – hiding a button
                is never the only protection.
              </p>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2">
              {SECURITY.map((item) => (
                <li
                  key={item}
                  className="flex gap-3 rounded-xl bg-white/5 p-4 text-sm text-slate-200 ring-1 ring-white/10"
                >
                  <Check className="mt-0.5 size-4 shrink-0 text-cyan-300" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ---------- call to action ---------- */}
      <section className="mx-auto max-w-6xl px-4 pb-24 text-center sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight text-slate-900">
          Ready to keep your files safe?
        </h2>
        <p className="mt-3 text-slate-600">Create a free account and upload your first file.</p>
        <Link
          to={loggedIn ? '/files' : '/register'}
          className="mt-8 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-3 font-medium text-white hover:bg-blue-700"
        >
          {loggedIn ? 'Open my files' : 'Create your account'}
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </section>

      <Footer />
    </div>
  );
}

function Header({ loggedIn }) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-100 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-8 px-4 sm:px-6">
        <Link to="/" aria-label="TrustShare home">
          <Logo />
        </Link>
        <nav className="hidden gap-6 text-sm text-slate-600 md:flex">
          <a href="#features" className="hover:text-slate-900">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-slate-900">
            How it works
          </a>
          <a href="#security" className="hover:text-slate-900">
            Security
          </a>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {loggedIn ? (
            <Link
              to="/files"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Open my files
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Log in
              </Link>
              <Link
                to="/register"
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function SectionTitle({ eyebrow, title, text }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-sm font-semibold tracking-wide text-blue-600 uppercase">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
        {title}
      </h2>
      <p className="mt-4 text-slate-600">{text}</p>
    </div>
  );
}

function Footer() {
  return (
    <footer className="border-t border-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:px-6">
        <Logo />
        <p>© 2026 TrustShare · Secure file sharing</p>
        <div className="flex gap-5">
          <Link to="/status" className="hover:text-slate-800">
            System status
          </Link>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-slate-800">
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
