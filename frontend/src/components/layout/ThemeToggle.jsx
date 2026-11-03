import { Moon, Sun } from 'lucide-react';

import { useTheme } from '../../theme/useTheme';

/** Sun/moon button in the workspace header: switches between light and dark mode. */
export default function ThemeToggle() {
  const { resolved, toggle } = useTheme();
  const dark = resolved === 'dark';
  const label = dark ? 'Switch to light mode' : 'Switch to dark mode';
  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
      aria-label={label}
      title={label}
    >
      {dark ? <Sun className="size-5" aria-hidden="true" /> : <Moon className="size-5" />}
    </button>
  );
}
