import { Eye, EyeOff } from 'lucide-react';
import { useId, useState } from 'react';

const INPUT =
  'block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 ' +
  'placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 ' +
  'focus:outline-none disabled:bg-slate-50';

/** Labelled input. type="password" gets a show/hide button; `icon` shows an icon on the left. */
export default function FormField({ label, type = 'text', hint, icon: Icon, ...inputProps }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const isPassword = type === 'password';

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        {Icon && (
          <Icon
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
        )}
        <input
          id={id}
          type={isPassword && visible ? 'text' : type}
          className={`${INPUT} ${isPassword ? 'pr-10' : ''} ${Icon ? 'pl-9' : ''}`}
          {...inputProps}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 hover:text-slate-600"
            aria-label={visible ? 'Hide password' : 'Show password'}
          >
            {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        )}
      </div>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
