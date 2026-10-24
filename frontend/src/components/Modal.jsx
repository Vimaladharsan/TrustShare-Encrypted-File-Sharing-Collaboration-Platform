import { X } from 'lucide-react';
import { useEffect, useRef } from 'react';

/**
 * Dialog: blurred backdrop, panel that pops in, closes on Escape, the ✕ button or a click on the
 * backdrop. The page behind doesn't scroll while it is open, and keyboard focus moves into it.
 */
export default function Modal({ title, onClose, children, width = 'max-w-md' }) {
  const panelRef = useRef(null);
  const pressedOnBackdrop = useRef(false);

  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';
    // Move focus into the dialog unless a field inside already took it (autoFocus).
    if (!panelRef.current?.contains(document.activeElement)) panelRef.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
    };
  }, []);

  return (
    <div
      className="animate-fade-in fixed inset-0 z-50 flex items-end justify-center bg-slate-950/40 p-4 backdrop-blur-[3px] sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      // Only a click that starts AND ends on the backdrop closes (not text selection drags).
      onMouseDown={(e) => (pressedOnBackdrop.current = e.target === e.currentTarget)}
      onMouseUp={(e) => pressedOnBackdrop.current && e.target === e.currentTarget && onClose()}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`max-h-[calc(100vh-2rem)] w-full ${width} animate-pop-in shadow-pop overflow-y-auto rounded-2xl bg-white p-6 ring-1 ring-slate-900/5 focus:outline-none`}
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold tracking-tight text-slate-950">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="-mt-1 -mr-2 rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
