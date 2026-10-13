import { ArrowDown, ArrowUp } from 'lucide-react';

import { fileIcon, formatBytes, formatDate } from '../../utils/format';
import ActionMenu from '../ActionMenu';

const COLUMNS = [
  { key: 'name', label: 'Name', className: '' },
  { key: null, label: 'Type', className: 'hidden sm:table-cell' },
  { key: 'size', label: 'Size', className: 'text-right' },
  { key: 'date', label: 'Uploaded', className: 'hidden md:table-cell' },
];

/**
 * File list as a table. Click a column header to sort.
 * actionsFor(file) returns the ⋮ menu items for that file.
 */
export default function FileTable({ files, sort, onSort, actionsFor }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500">
          <tr>
            {COLUMNS.map((col) => (
              <th key={col.label} className={`px-4 py-3 ${col.className}`} scope="col">
                {col.key && onSort ? (
                  <button
                    type="button"
                    onClick={() => onSort(col.key)}
                    className="inline-flex items-center gap-1 hover:text-slate-800"
                  >
                    {col.label}
                    {sort?.by === col.key &&
                      (sort.order === 'asc' ? (
                        <ArrowUp className="size-3" />
                      ) : (
                        <ArrowDown className="size-3" />
                      ))}
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
          {files.map((file) => {
            const { Icon, color } = fileIcon(file.category);
            return (
              <tr key={file.id} className="hover:bg-slate-50">
                <td className="max-w-0 px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Icon className={`size-5 shrink-0 ${color}`} aria-hidden="true" />
                    <span className="truncate font-medium text-slate-800" title={file.name}>
                      {file.name}
                    </span>
                  </div>
                </td>
                <td className="hidden px-4 py-3 text-slate-500 uppercase sm:table-cell">
                  {file.extension}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap text-slate-500">
                  {formatBytes(file.size_bytes)}
                </td>
                <td className="hidden px-4 py-3 whitespace-nowrap text-slate-500 md:table-cell">
                  {formatDate(file.created_at)}
                </td>
                <td className="px-4 py-3">
                  <ActionMenu items={actionsFor(file)} label={`Actions for ${file.name}`} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
