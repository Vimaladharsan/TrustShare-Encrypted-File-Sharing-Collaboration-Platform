import { MoreVertical } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const MENU_WIDTH = 176; // px (w-44)
const ITEM_HEIGHT = 36; // px per menu row (approximate, for flipping upwards)

/**
 * The ⋮ menu on each file/folder row.
 * items: [{ label, icon: Icon, onClick, danger? }] – items set to null/false are skipped.
 *
 * The menu is positioned relative to the window (position: fixed), so a parent with
 * overflow: hidden (like the rounded file table) can't cut it off. It opens upwards
 * when there isn't enough room below the button.
 */
export default function ActionMenu({ items, label = 'Actions' }) {
  const [position, setPosition] = useState(null); // null = closed
  const buttonRef = useRef(null);
  const menuRef = useRef(null);

  const visible = items.filter(Boolean);

  useEffect(() => {
    if (!position) return undefined;
    const close = (event) => {
      if (menuRef.current?.contains(event.target) || buttonRef.current?.contains(event.target)) {
        return;
      }
      setPosition(null);
    };
    const closeNow = () => setPosition(null);
    document.addEventListener('mousedown', close);
    window.addEventListener('scroll', closeNow, true); // fixed menus would drift on scroll
    window.addEventListener('resize', closeNow);
    return () => {
      document.removeEventListener('mousedown', close);
      window.removeEventListener('scroll', closeNow, true);
      window.removeEventListener('resize', closeNow);
    };
  }, [position]);

  if (visible.length === 0) return null;

  function toggle(event) {
    event.stopPropagation(); // don't also open the folder/row
    if (position) {
      setPosition(null);
      return;
    }
    const rect = buttonRef.current.getBoundingClientRect();
    const menuHeight = visible.length * ITEM_HEIGHT + 8;
    const opensUp = rect.bottom + menuHeight + 8 > window.innerHeight;
    setPosition({
      top: opensUp ? rect.top - menuHeight - 4 : rect.bottom + 4,
      left: Math.max(8, rect.right - MENU_WIDTH),
    });
  }

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={toggle}
        className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        aria-label={label}
        aria-expanded={Boolean(position)}
      >
        <MoreVertical className="size-4" />
      </button>
      {position && (
        <ul
          ref={menuRef}
          style={{ top: position.top, left: position.left, width: MENU_WIDTH }}
          className="fixed z-50 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {visible.map(({ label: itemLabel, icon: Icon, onClick, danger }) => (
            <li key={itemLabel}>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setPosition(null);
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
    </>
  );
}
