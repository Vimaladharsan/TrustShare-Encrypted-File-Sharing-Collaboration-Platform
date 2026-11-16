import { ChevronRight, HardDrive } from 'lucide-react';
import { Link } from 'react-router';

import { useMoveDrop } from '../../utils/dragMove';

/** Page title for My Files: a small trail (My Files › Finance ›) above the current folder name.
 *  Optional `onMoveInto(payload, { id, name })`: files / folders can be dropped on a trail link to
 *  move them up into that folder (id null = My Files). */
export default function Breadcrumbs({ crumbs, rootLabel = 'My Files', onMoveInto }) {
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
              <CrumbLink part={part} onMoveInto={onMoveInto} />
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

function CrumbLink({ part, onMoveInto }) {
  const { over, dropProps } = useMoveDrop(
    (payload) => onMoveInto?.(payload, part),
    (payload) => Boolean(onMoveInto) && payload.folder?.id !== part.id,
  );
  return (
    <Link
      to={part.id ? `/folders/${part.id}` : '/files'}
      {...(onMoveInto ? dropProps : {})}
      className={`truncate rounded-md px-1 transition hover:text-blue-600 ${
        over ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-500/40' : 'text-slate-500'
      }`}
    >
      {part.name}
    </Link>
  );
}
