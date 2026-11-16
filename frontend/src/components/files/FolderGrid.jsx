import { Folder } from 'lucide-react';

import { DROP_HIGHLIGHT, startMoveDrag, useMoveDrop } from '../../utils/dragMove';
import ActionMenu from '../ActionMenu';

/**
 * Folder cards; clicking a card opens the folder.
 * Optional selection: pass `selected` (a Set of ids) and `onToggle(id)` to show checkboxes.
 * Optional drag and drop: `onMoveInto(payload, folder)` makes every card a drop target for dragged
 * files / folders; `draggable` lets the cards themselves be dragged into another folder.
 */
export default function FolderGrid({
  folders,
  onOpen,
  actionsFor,
  selected,
  onToggle,
  onMoveInto,
  draggable = false,
}) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {folders.map((folder) => (
        <li key={folder.id}>
          <FolderCard
            folder={folder}
            onOpen={onOpen}
            actionsFor={actionsFor}
            selected={selected}
            onToggle={onToggle}
            onMoveInto={onMoveInto}
            draggable={draggable}
          />
        </li>
      ))}
    </ul>
  );
}

function FolderCard({ folder, onOpen, actionsFor, selected, onToggle, onMoveInto, draggable }) {
  const selectable = Boolean(selected && onToggle);
  const isSelected = selectable && selected.has(folder.id);
  const { over, dropProps } = useMoveDrop(
    (payload) => onMoveInto?.(payload, folder),
    (payload) => Boolean(onMoveInto) && payload.folder?.id !== folder.id,
  );
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(folder)}
      onKeyDown={(e) => e.key === 'Enter' && onOpen(folder)}
      draggable={draggable}
      onDragStart={
        draggable
          ? (e) => startMoveDrag(e, { folder: { id: folder.id, name: folder.name } }, folder.name)
          : undefined
      }
      {...(onMoveInto ? dropProps : {})}
      className={`group shadow-card hover:shadow-card-hover flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition duration-150 hover:-translate-y-0.5 ${
        over
          ? DROP_HIGHLIGHT
          : isSelected
            ? 'border-blue-400 bg-white ring-2 ring-blue-500/20'
            : 'border-slate-200/80 bg-white hover:border-slate-300'
      }`}
    >
      {selectable && (
        <input
          type="checkbox"
          checked={selected.has(folder.id)}
          onChange={() => onToggle(folder.id)}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${folder.name}`}
          className="size-4 shrink-0 rounded border-slate-300 accent-blue-600"
        />
      )}
      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-sky-50 to-blue-100 ring-1 ring-blue-100 ring-inset">
        <Folder className="size-5 fill-blue-200 text-blue-600" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-slate-800 group-hover:text-slate-950">
          {folder.name}
        </span>
        <span className="block text-xs text-slate-400">
          {over ? 'Drop to move here' : 'Folder'}
        </span>
      </span>
      {actionsFor && <ActionMenu items={actionsFor(folder)} label={`Actions for ${folder.name}`} />}
    </div>
  );
}
