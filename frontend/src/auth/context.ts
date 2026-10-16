// Auth context + hook (F2). Kept separate from the <AuthProvider> component so
// the provider file only exports a component (react-refresh/only-export-components).
import { createContext, useContext } from "react";
import type { AuthUser, Role } from "@/api/types";

export interface AuthContextValue {
  /** The logged-in user, or null when unauthenticated. Held in memory only. */
  user: AuthUser | null;
  /** Convenience accessor for the user's role (null when logged out). */
  role: Role | null;
  /** True while the initial getMe() bootstrap is in flight. */
  loading: boolean;
  /** POST /api/auth/login. Throws ApiError (401) on bad credentials. */
  login: (username: string, password: string) => Promise<void>;
  /** POST /api/auth/logout, then clears the in-memory user. */
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** Access the auth context. Throws if used outside <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
