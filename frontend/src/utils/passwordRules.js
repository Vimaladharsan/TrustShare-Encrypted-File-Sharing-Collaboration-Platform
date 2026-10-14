// Same rules as the backend (app/schemas/auth.py → password_problem). The backend checks again –
// this is only so the user sees what's still missing while typing.
export const PASSWORD_RULES = [
  { label: 'At least 10 characters', test: (p) => p.length >= 10 },
  { label: 'An uppercase and a lowercase letter', test: (p) => /[a-z]/.test(p) && /[A-Z]/.test(p) },
  { label: 'A number', test: (p) => /\d/.test(p) },
  { label: 'A symbol', test: (p) => /[^A-Za-z0-9]/.test(p) },
];

export function passwordMeetsRules(password) {
  return PASSWORD_RULES.every((rule) => rule.test(password));
}
