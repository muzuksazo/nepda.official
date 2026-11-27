import { createContext, useContext } from 'react';
import type { AuthUserResponse, QuotaStatus } from '../api/generated/model';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUserResponse | null;
  quota: QuotaStatus | null;
  isSubmitting: boolean;
  error: string | null;
  clientId: string;
  signInWithCredential: (credential: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return ctx;
}
