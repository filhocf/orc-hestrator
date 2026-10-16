import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import Placeholder from "@/components/Placeholder";
import Login from "@/pages/Login";
import Overview from "@/pages/Overview";
import LiveTeam from "@/pages/LiveTeam";
import Board from "@/pages/Board";
import Arcs from "@/pages/Arcs";
import Graph from "@/pages/Graph";
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
        TODO: auth real (OAuth2 / sessão) = futuro. For v1 the app shell is open
        (no hard guard) and auth is a localStorage stub (see src/auth/stub.ts).
        When real auth lands, wrap <Layout /> in a <ProtectedRoute> that calls
        isAuthenticated() and <Navigate to="/login" replace /> on failure:
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}> ... </Route>
      */}
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
            ) : (
              <Placeholder title={screen.label} />
            );
          return <Route key={screen.path} path={screen.path} element={element} />;
        })}
        <Route path="/task/:id" element={<Placeholder title="Detalhe da tarefa" />} />
        <Route path="*" element={<Placeholder title="Página não encontrada" />} />
      </Route>
    </Routes>
  );
}
