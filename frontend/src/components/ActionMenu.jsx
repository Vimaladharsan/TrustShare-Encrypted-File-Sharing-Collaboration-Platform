import { MoreVertical } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

/**
 * The ⋮ menu on each file/folder row.
 * items: [{ label, icon: Icon, onClick, danger? }] – items set to null/false are skipped.
 */
export default function ActionMenu({ items, label = 'Actions' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const visible = items.filter(Boolean);
  if (visible.length === 0) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation(); // don't also open the folder/row
          setOpen((v) => !v);
        }}
        className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        aria-label={label}
        aria-expanded={open}
      >
        <MoreVertical className="size-4" />
      </button>
      {open && (
        <ul className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {visible.map(({ label: itemLabel, icon: Icon, onClick, danger }) => (
            <li key={itemLabel}>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpen(false);
                  onClick();
                }}
                className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                  danger ? 'text-red-600' : 'text-slate-700'
                }`}
              >
                {Icon && <Icon className="size-4" aria-hidden="true" />}
                {itemLabel}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
