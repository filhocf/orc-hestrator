// Auth STUB (v1) — session flag only. No real authentication yet.
//
// TODO: auth real (OAuth2 / sessão de servidor) = futuro.
//   The backend has no /api login endpoint yet. When it lands, replace this
//   stub with a real credential exchange + token/session handling and wire a
//   hard ProtectedRoute around the app shell (see App.tsx comment). For now we
//   only persist a boolean "logged in" flag in localStorage so the UI flow
//   (login -> /overview, and /login redirect when already "logged in") works.

const STORAGE_KEY = "orc_auth";

/** True when a (stub) session flag is present. */
export function isAuthenticated(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    // localStorage can throw in private-mode / SSR-ish contexts; treat as logged out.
    return false;
  }
}

/**
 * Persist the stub session flag. Optionally records the username for display.
 * TODO (auth real): exchange credentials for a real token here.
 */
export function login(username: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
    if (username) localStorage.setItem(`${STORAGE_KEY}_user`, username);
  } catch {
    // Non-fatal: navigation still proceeds; a hard guard is future work.
  }
}

/** Clear the stub session flag. */
export function logout(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(`${STORAGE_KEY}_user`);
  } catch {
    // Non-fatal.
  }
}
