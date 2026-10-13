import { Folder } from 'lucide-react';

import ActionMenu from '../ActionMenu';

/**
 * Folder cards; clicking a card opens the folder.
 * Optional selection: pass `selected` (a Set of ids) and `onToggle(id)` to show checkboxes.
 */
export default function FolderGrid({ folders, onOpen, actionsFor, selected, onToggle }) {
  const selectable = Boolean(selected && onToggle);
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {folders.map((folder) => (
        <li key={folder.id}>
          <div
            role="button"
            tabIndex={0}
            onClick={() => onOpen(folder)}
            onKeyDown={(e) => e.key === 'Enter' && onOpen(folder)}
            className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3 hover:border-blue-300 ${
              selectable && selected.has(folder.id)
                ? 'border-blue-400 bg-blue-50'
                : 'border-slate-200 bg-white hover:bg-blue-50/40'
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
            <Folder className="size-5 shrink-0 fill-blue-100 text-blue-500" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">
              {folder.name}
            </span>
            {actionsFor && (
              <ActionMenu items={actionsFor(folder)} label={`Actions for ${folder.name}`} />
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
