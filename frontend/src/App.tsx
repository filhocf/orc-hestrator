import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import Placeholder from "@/components/Placeholder";
import Login from "@/pages/Login";
import Overview from "@/pages/Overview";
import LiveTeam from "@/pages/LiveTeam";
import Board from "@/pages/Board";
import Arcs from "@/pages/Arcs";
import Graph from "@/pages/Graph";
import Admin from "@/pages/Admin";
import Profile from "@/pages/Profile";
import TaskDetail from "@/pages/TaskDetail";
import { NAV_SCREENS } from "@/nav";

/**
 * Routing for the 9 screens.
 * - Login is rendered OUTSIDE the Layout shell.
 * - The 7 sidebar screens are routed children of Layout.
 * - "Detalhe da tarefa" is a modal-style route (/task/:id) that also lives inside the shell.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/*
        Real auth guard (F2): ProtectedRoute calls useAuth(); while getMe()
        bootstraps it shows a spinner, and <Navigate to="/login" replace /> when
        there is no server session. /login stays OUTSIDE the guard. The session
        truth is the HttpOnly orc_session cookie (see src/auth/AuthContext.tsx).
      */}
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        {NAV_SCREENS.map((screen) => {
          const element =
            screen.path === "/overview" ? (
              <Overview />
            ) : screen.path === "/live" ? (
              <LiveTeam />
            ) : screen.path === "/board" ? (
              <Board />
            ) : screen.path === "/arcs" ? (
              <Arcs />
            ) : screen.path === "/graph" ? (
              <Graph />
            ) : screen.path === "/admin" ? (
              <Admin />
            ) : screen.path === "/profile" ? (
              <Profile />
            ) : (
              <Placeholder title={screen.label} />
            );
          return <Route key={screen.path} path={screen.path} element={element} />;
        })}
        <Route path="/task/:id" element={<TaskDetail />} />
        <Route path="*" element={<Placeholder title="Página não encontrada" />} />
        </Route>
      </Route>
    </Routes>
  );
}
