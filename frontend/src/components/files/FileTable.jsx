import { ArrowDown, ArrowUp, ArrowUpDown, Star } from 'lucide-react';

import { formatBytes, formatDate } from '../../utils/format';
import ActionMenu from '../ActionMenu';
import FileIcon from './FileIcon';

const COLUMNS = [
  { key: 'name', label: 'Name', className: '' },
  { key: null, label: 'Type', className: 'hidden sm:table-cell' },
  { key: 'size', label: 'Size', className: 'hidden text-right sm:table-cell' },
  { key: 'date', label: 'Uploaded', className: 'hidden md:table-cell' },
];

/**
 * File list as a table. Click a column header to sort.
 * actionsFor(file) returns the ⋮ menu items for that file.
 * Optional selection: pass `selected` (a Set of ids) and `onToggle(id)` to show checkboxes.
 * Optional `onOpen(file)`: the file name becomes clickable (opens the preview).
 */
export default function FileTable({ files, sort, onSort, actionsFor, selected, onToggle, onOpen }) {
  const selectable = Boolean(selected && onToggle);
  const allSelected = selectable && files.length > 0 && files.every((f) => selected.has(f.id));
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="eyebrow border-b border-slate-200 bg-slate-50/80 text-left !text-slate-500">
          <tr>
            {selectable && (
              <th className="w-10 px-4 py-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={() =>
                    files.forEach((f) => selected.has(f.id) === allSelected && onToggle(f.id))
                  }
                  aria-label="Select all files"
                  className="size-4 rounded border-slate-300 accent-blue-600"
                />
              </th>
            )}
            {COLUMNS.map((col) => (
              <th
                key={col.label}
                className={`px-4 py-3 font-semibold ${col.className}`}
                scope="col"
              >
                {col.key && onSort ? (
                  <button
                    type="button"
                    onClick={() => onSort(col.key)}
                    className={`group inline-flex items-center gap-1 uppercase transition hover:text-slate-900 ${
                      sort?.by === col.key ? 'text-slate-900' : ''
                    }`}
                  >
                    {col.label}
                    {sort?.by === col.key ? (
                      sort.order === 'asc' ? (
                        <ArrowUp className="size-3" />
                      ) : (
                        <ArrowDown className="size-3" />
                      )
                    ) : (
                      <ArrowUpDown className="size-3 opacity-0 transition group-hover:opacity-60" />
                    )}
                  </button>
                ) : (
                  col.label
                )}
              </th>
            ))}
            <th className="w-12 px-4 py-3">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {files.map((file) => (
            <tr
              key={file.id}
              className={`group transition-colors ${
                selectable && selected.has(file.id) ? 'bg-blue-50/60' : 'hover:bg-slate-50/80'
              }`}
            >
              {selectable && (
                <td className="px-4 py-2.5">
                  <input
                    type="checkbox"
                    checked={selected.has(file.id)}
                    onChange={() => onToggle(file.id)}
                    aria-label={`Select ${file.name}`}
                    className="size-4 rounded border-slate-300 accent-blue-600"
                  />
                </td>
              )}
              <td className="max-w-0 px-4 py-2.5">
                <div className="flex items-center gap-3">
                  <FileIcon category={file.category} size="sm" />
                  <span className="min-w-0">
                    {onOpen ? (
                      <button
                        type="button"
                        onClick={() => onOpen(file)}
                        className="block max-w-full truncate text-left font-medium text-slate-800 transition hover:text-blue-600"
                        title={`Preview ${file.name}`}
                      >
                        {file.name}
                      </button>
                    ) : (
                      <span className="block truncate font-medium text-slate-800" title={file.name}>
                        {file.name}
                      </span>
                    )}
                    <span className="block text-xs text-slate-400 sm:hidden">
                      {file.extension.toUpperCase()} · {formatBytes(file.size_bytes)}
                    </span>
                  </span>
                  {file.is_favorite && (
                    <Star
                      className="size-3.5 shrink-0 fill-amber-400 text-amber-400"
                      aria-label="Favorite"
                    />
                  )}
                </div>
              </td>
              <td className="hidden px-4 py-2.5 sm:table-cell">
                <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold text-slate-500 uppercase">
                  {file.extension}
                </span>
              </td>
              <td className="hidden px-4 py-2.5 text-right whitespace-nowrap text-slate-500 sm:table-cell">
                {formatBytes(file.size_bytes)}
              </td>
              <td className="hidden px-4 py-2.5 whitespace-nowrap text-slate-500 md:table-cell">
                {formatDate(file.created_at)}
              </td>
              <td className="px-4 py-2.5 text-right">
                <ActionMenu items={actionsFor(file)} label={`Actions for ${file.name}`} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
