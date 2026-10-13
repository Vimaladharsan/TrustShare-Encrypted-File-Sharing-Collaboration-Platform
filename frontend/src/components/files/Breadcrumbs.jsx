import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router';

/** My Files › Finance › Tax 2026 – every part except the last is a link. */
export default function Breadcrumbs({ crumbs, rootLabel = 'My Files' }) {
  const parts = [{ id: null, name: rootLabel }, ...crumbs];
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 flex-wrap items-center gap-1 text-lg">
      {parts.map((part, index) => {
        const last = index === parts.length - 1;
        return (
          <span key={part.id ?? 'root'} className="flex min-w-0 items-center gap-1">
            {index > 0 && <ChevronRight className="size-4 shrink-0 text-slate-400" />}
            {last ? (
              <span className="truncate font-semibold text-slate-900" aria-current="page">
                {part.name}
              </span>
            ) : (
              <Link
                to={part.id ? `/folders/${part.id}` : '/files'}
                className="truncate text-slate-500 hover:text-slate-900"
              >
                {part.name}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
