// Real authentication provider (F2).
//
// The source of truth for "am I logged in?" is the server, discovered via
// getMe() against the HttpOnly `orc_session` cookie — NOT localStorage. JS
// cannot read the cookie, so on mount we call getMe() once to bootstrap:
//   - 200 { user } -> authenticated, user/role held in React state (memory only)
//   - 401          -> not authenticated (expected, swallowed)
//
// login()/logout() hit the real endpoints and update the in-memory user. A
// mid-session 401 on any other /api call is handled globally by the client's
// unauthorized handler, which we wire to clear the user here.
//
// The context object + useAuth() hook live in ./context (a non-component module)
// so this file only exports a component (react-refresh/only-export-components).
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  setUnauthorizedHandler,
} from "@/api/client";
import type { AuthUser } from "@/api/types";
import { AuthContext } from "@/auth/context";
import type { AuthContextValue } from "@/auth/context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Bootstrap: discover the session from the cookie exactly once on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { user: me } = await getMe();
        if (!cancelled) setUser(me);
      } catch {
        // 401 (or network) -> treated as logged out.
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // A mid-session 401 on any protected endpoint means the server session is
  // gone; drop the in-memory user so ProtectedRoute bounces to /login.
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const { user: me } = await apiLogin(username, password);
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      // Clear local state regardless of the network result.
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, role: user?.role ?? null, loading, login, logout }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
