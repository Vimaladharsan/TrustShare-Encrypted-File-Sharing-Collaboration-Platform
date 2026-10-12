import { createContext } from 'react';

/**
 * Who is logged in, shared with the whole app.
 * status: 'loading' (checking the session) | 'authenticated' | 'anonymous'
 */
export const AuthContext = createContext(null);
