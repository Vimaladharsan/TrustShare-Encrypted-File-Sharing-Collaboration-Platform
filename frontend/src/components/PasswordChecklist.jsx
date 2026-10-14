import { Check, Circle } from 'lucide-react';

import { PASSWORD_RULES } from '../utils/passwordRules';

/** Live list of the password rules, ticking each one off as it's met. */
export default function PasswordChecklist({ password }) {
  return (
    <ul className="mt-2 space-y-1">
      {PASSWORD_RULES.map((rule) => {
        const ok = rule.test(password);
        return (
          <li
            key={rule.label}
            className={`flex items-center gap-2 text-xs ${ok ? 'text-green-600' : 'text-slate-500'}`}
          >
            {ok ? <Check className="size-3.5" /> : <Circle className="size-3.5" />}
            {rule.label}
          </li>
        );
      })}
    </ul>
  );
}
