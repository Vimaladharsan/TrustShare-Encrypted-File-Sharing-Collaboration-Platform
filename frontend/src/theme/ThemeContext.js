import { createContext } from 'react';

// { preference: 'light' | 'dark' | 'system', resolved: 'light' | 'dark', setPreference(p), toggle() }
export const ThemeContext = createContext(null);
