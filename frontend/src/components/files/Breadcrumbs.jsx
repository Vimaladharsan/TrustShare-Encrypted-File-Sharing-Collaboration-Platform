import { ChevronRight, HardDrive } from 'lucide-react';
import { Link } from 'react-router';

/** Page title for My Files: a small trail (My Files › Finance ›) above the current folder name. */
export default function Breadcrumbs({ crumbs, rootLabel = 'My Files' }) {
  const parts = [{ id: null, name: rootLabel }, ...crumbs];
  const current = parts[parts.length - 1];
  const trail = parts.slice(0, -1);
  return (
    <div className="min-w-0">
      {trail.length > 0 && (
        <nav
          aria-label="Breadcrumb"
          className="mb-1 flex min-w-0 flex-wrap items-center gap-1 text-sm"
        >
          {trail.map((part, index) => (
            <span key={part.id ?? 'root'} className="flex min-w-0 items-center gap-1">
              {index === 0 && <HardDrive className="size-3.5 text-slate-400" aria-hidden="true" />}
              <Link
                to={part.id ? `/folders/${part.id}` : '/files'}
                className="truncate text-slate-500 transition hover:text-blue-600"
              >
                {part.name}
              </Link>
              <ChevronRight className="size-3.5 shrink-0 text-slate-300" aria-hidden="true" />
            </span>
          ))}
        </nav>
      )}
      <h1
        className="truncate text-2xl font-semibold tracking-tight text-slate-950"
        aria-current="page"
      >
        {current.name}
      </h1>
    </div>
  );
}
