import { useRef, useState } from 'react';

/**
 * Drag and drop to move things in My Files (browser drag-and-drop API, desktop only – on phones
 * the ⋮ "Move to…" menu does the same).
 *
 * What is dragged travels in our own data type, so dropping files from the computer (uploads) or
 * text onto a folder is ignored here. Payload: { files: [ids] } or { folder: { id, name } }.
 */
const TYPE = 'application/x-trustshare-move';

export function startMoveDrag(event, payload, label) {
  event.dataTransfer.setData(TYPE, JSON.stringify(payload));
  event.dataTransfer.effectAllowed = 'move';
  // A small "3 files" chip under the pointer instead of a screenshot of the whole row.
  const chip = document.createElement('div');
  chip.textContent = label;
  chip.style.cssText =
    'position:fixed;top:-100px;left:0;padding:6px 12px;border-radius:9999px;' +
    'background:#2563eb;color:#fff;font:600 13px system-ui,sans-serif;white-space:nowrap';
  document.body.appendChild(chip);
  event.dataTransfer.setDragImage(chip, 12, 12);
  setTimeout(() => chip.remove(), 0);
}

const isMoveDrag = (event) => event.dataTransfer.types.includes(TYPE);

/**
 * Makes an element a drop target. `onDrop(payload)` runs with what was dropped;
 * `accepts(payload)` (optional) can refuse e.g. a folder dropped onto itself.
 * Returns { over, dropProps } – spread dropProps on the element, use `over` for the highlight.
 */
export function useMoveDrop(onDrop, accepts = () => true) {
  const [over, setOver] = useState(false);
  const depth = useRef(0); // enter/leave also fire for child elements – count them

  const dropProps = {
    onDragEnter(event) {
      if (!isMoveDrag(event)) return;
      event.preventDefault();
      depth.current += 1;
      setOver(true);
    },
    onDragOver(event) {
      if (!isMoveDrag(event)) return;
      event.preventDefault(); // allows the drop
      event.dataTransfer.dropEffect = 'move';
    },
    onDragLeave(event) {
      if (!isMoveDrag(event)) return;
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setOver(false);
    },
    onDrop(event) {
      if (!isMoveDrag(event)) return;
      event.preventDefault();
      depth.current = 0;
      setOver(false);
      let payload;
      try {
        payload = JSON.parse(event.dataTransfer.getData(TYPE));
      } catch {
        return;
      }
      if (accepts(payload)) onDrop(payload);
    },
  };
  return { over, dropProps };
}

/** Highlight classes for a drop target while something is dragged over it. */
export const DROP_HIGHLIGHT = 'border-blue-500 bg-blue-50 ring-4 ring-blue-500/25 scale-[1.02]';
