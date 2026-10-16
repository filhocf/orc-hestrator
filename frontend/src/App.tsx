import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import Placeholder from "@/components/Placeholder";
import Login from "@/pages/Login";
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
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        {NAV_SCREENS.map((screen) => (
          <Route key={screen.path} path={screen.path} element={<Placeholder title={screen.label} />} />
        ))}
        <Route path="/task/:id" element={<Placeholder title="Detalhe da tarefa" />} />
        <Route path="*" element={<Placeholder title="Página não encontrada" />} />
      </Route>
    </Routes>
  );
}
