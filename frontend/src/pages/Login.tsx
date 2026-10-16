import { useNavigate } from "react-router-dom";

/** Login screen — rendered OUTSIDE the app shell (no sidebar/topbar). Placeholder for now. */
export default function Login() {
  const navigate = useNavigate();
  return (
    <div className="flex h-full w-full items-center justify-center bg-surface p-6">
      <div className="w-full max-w-sm rounded-card border border-surface-border bg-surface-raised p-8">
        <div className="mb-6 flex flex-col items-center gap-3">
          <img src="/mascote.svg" alt="Orc" className="h-14 w-14" />
          <h1 className="font-display text-headline-md text-content">Orchestrator Control Hub</h1>
          <p className="text-body-sm text-content-muted">Entre para gerenciar o time de agentes</p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/overview")}
          className="w-full rounded-card bg-primary py-2.5 font-display text-label-lg text-primary-contrast transition-colors hover:bg-primary-hover"
        >
          Entrar
        </button>
        <p className="mt-4 text-center text-body-sm text-content-subtle">Autenticação em breve.</p>
      </div>
    </div>
  );
}
