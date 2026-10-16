import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/auth/context";

/**
 * Hard auth guard around the app shell (F2).
 *  - While the initial getMe() bootstrap runs -> a centered spinner (we do NOT
 *    know yet whether there is a session, so neither render the shell nor bounce).
 *  - No authenticated user -> redirect to /login (replace, so Back doesn't loop).
 *  - Authenticated -> render the nested routes via <Outlet/>.
 *
 * Used as a layout route element in App.tsx, wrapping <Layout/>.
 */
export default function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div
        role="status"
        aria-label="Verificando sessão"
        className="flex h-full w-full items-center justify-center bg-surface text-content"
      >
        <span className="material-symbol animate-spin text-[32px] text-primary">
          progress_activity
        </span>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
