import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { isAuthenticated, login } from "@/auth/stub";

/**
 * Login screen — rendered OUTSIDE the app shell (no sidebar/topbar).
 * Ported 1:1 from the Stitch mockup:
 *   docs/design/stitch/login_orc_hestrator/code.html
 *
 * Auth is a STUB (v1): basic non-empty validation, then a localStorage session
 * flag + navigation to /overview.
 *
 * TODO: auth real (OAuth2 / sessão) = futuro. No /api login call yet (backend
 * has no auth endpoint). The "Esqueci minha senha" / "Entrar com SSO" actions
 * are visual-only placeholders until the real flow lands.
 */
export default function Login() {
  const navigate = useNavigate();

  const [usuario, setUsuario] = useState("");
  const [senha, setSenha] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  // If already "logged in" (stub flag present), skip the login screen.
  useEffect(() => {
    if (isAuthenticated()) navigate("/overview", { replace: true });
  }, [navigate]);

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Basic validation: both fields required (stub — no credential check).
    if (!usuario.trim() || !senha.trim()) {
      setError("Preencha usuário e senha para continuar.");
      return;
    }
    setError("");
    login(usuario.trim());
    navigate("/overview", { replace: true });
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-background font-sans text-on-surface antialiased">
      <main className="w-full">
        <div className="relative flex min-h-[calc(100vh-2rem)] w-full flex-col items-center justify-center overflow-hidden p-4 sm:p-6 lg:p-8">
          {/* Ambient glow accents */}
          <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-primary-container/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-secondary-container/20 blur-3xl" />

          <div className="relative z-10 w-full max-w-md">
            <div className="relative overflow-hidden rounded-xl bg-surface-container p-8 shadow-xl sm:p-10">
              {/* Amber top gradient bar */}
              <div className="absolute left-0 right-0 top-0 h-1.5 bg-gradient-to-r from-primary-container via-primary to-primary-container" />

              {/* Header: mascot + brand */}
              <div className="mb-8 flex flex-col items-center text-center">
                <div className="group relative mb-4 h-24 w-24 cursor-default">
                  <div className="absolute inset-0 rounded-full bg-primary-container/20 blur-md transition-all group-hover:blur-lg" />
                  <div className="relative h-24 w-24 overflow-hidden rounded-full bg-surface-container-high p-1 shadow-md">
                    {/* Mascot: LOCAL asset (public/), not the googleusercontent URL. */}
                    <img
                      alt="Orc[hestrator] Mascote Oficial"
                      className="h-full w-full rounded-full object-cover"
                      src="/mascote.png"
                    />
                  </div>
                  <span className="absolute bottom-0 right-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#56e5a9] shadow-sm">
                    <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-surface-container-lowest" />
                  </span>
                </div>

                <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-surface-variant px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
                  <span
                    className="material-symbol text-[14px] text-primary-container"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    construction
                  </span>
                  Ambiente de Orquestração
                </div>

                <h1 className="flex items-center justify-center gap-1 font-display text-[28px] font-bold leading-[36px] tracking-tight text-on-surface">
                  <span>Orc</span>
                  <span className="font-extrabold text-primary-container">[</span>
                  <span>hestrator</span>
                  <span className="font-extrabold text-primary-container">]</span>
                </h1>
                <p className="mt-2 max-w-xs text-[14px] leading-relaxed text-secondary">
                  Missão de controle colaborativa entre humanos e agentes de IA
                </p>
              </div>

              {/* Login form */}
              <form className="space-y-5" id="loginForm" onSubmit={handleLogin} noValidate>
                <div className="space-y-1.5">
                  <label
                    className="block text-[12px] font-medium text-on-surface"
                    htmlFor="usuario"
                  >
                    Usuário
                  </label>
                  <div className="relative flex items-center">
                    <span className="material-symbol pointer-events-none absolute left-3.5 text-[20px] text-secondary">
                      person
                    </span>
                    <input
                      className="w-full rounded-lg bg-surface-container-low py-2.5 pl-11 pr-4 text-[14px] text-on-surface shadow-sm transition-all placeholder:text-secondary-fixed-dim/50 focus:bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-primary-container/40"
                      id="usuario"
                      name="usuario"
                      placeholder="ex: claudio.gerente ou seu email"
                      type="text"
                      value={usuario}
                      onChange={(e) => setUsuario(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label
                      className="block text-[12px] font-medium text-on-surface"
                      htmlFor="senha"
                    >
                      Senha
                    </label>
                    <a
                      className="text-[12px] font-semibold text-primary transition-colors hover:text-primary-container focus:outline-none"
                      href="#"
                    >
                      Esqueci minha senha
                    </a>
                  </div>
                  <div className="relative flex items-center">
                    <span className="material-symbol pointer-events-none absolute left-3.5 text-[20px] text-secondary">
                      lock
                    </span>
                    <input
                      className="w-full rounded-lg bg-surface-container-low py-2.5 pl-11 pr-11 text-[14px] text-on-surface shadow-sm transition-all placeholder:text-secondary-fixed-dim/50 focus:bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-primary-container/40"
                      id="senha"
                      name="senha"
                      placeholder="••••••••••••"
                      type={showPassword ? "text" : "password"}
                      value={senha}
                      onChange={(e) => setSenha(e.target.value)}
                    />
                    <button
                      aria-label="Mostrar ou ocultar senha"
                      className="absolute right-3.5 rounded p-1 text-secondary transition-colors hover:text-on-surface focus:outline-none"
                      id="togglePassword"
                      onClick={() => setShowPassword((v) => !v)}
                      type="button"
                    >
                      <span className="material-symbol text-[20px]">
                        {showPassword ? "visibility_off" : "visibility"}
                      </span>
                    </button>
                  </div>
                </div>

                {error && (
                  <p role="alert" className="text-[12px] font-medium text-status-blocked">
                    {error}
                  </p>
                )}

                <button
                  className="group mt-2 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-primary-container px-4 py-3 text-[16px] font-semibold text-on-primary shadow-md transition-all hover:bg-primary-fixed-dim hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary-container focus:ring-offset-2 focus:ring-offset-surface-container active:bg-primary-container"
                  id="submitBtn"
                  type="submit"
                >
                  <span>Entrar</span>
                  <span className="material-symbol text-[20px] transition-transform group-hover:translate-x-1">
                    arrow_forward
                  </span>
                </button>
              </form>

              {/* "ou" divider */}
              <div className="relative my-6 flex items-center justify-center">
                <div className="absolute inset-0 flex items-center">
                  <div className="h-[1px] w-full bg-surface-variant" />
                </div>
                <span className="relative bg-surface-container px-3 text-[11px] font-semibold uppercase tracking-wider text-secondary">
                  ou
                </span>
              </div>

              {/* SSO (visual placeholder — TODO: auth real) */}
              <div>
                <button
                  className="flex w-full items-center justify-center gap-2.5 rounded-lg bg-surface-container-high px-4 py-2.5 text-[14px] font-semibold text-on-surface shadow-sm transition-all hover:bg-surface-bright hover:shadow focus:outline-none focus:ring-2 focus:ring-secondary-fixed-dim/30 active:bg-surface-container-high"
                  type="button"
                >
                  <span className="material-symbol text-[20px] text-primary-container">key</span>
                  <span>Entrar com SSO</span>
                </button>
              </div>

              {/* Footer strip */}
              <div className="-mx-8 -mb-10 mt-8 flex items-center justify-center gap-2 rounded-b-xl bg-surface-container-low/60 p-5 pt-4 text-center">
                <span className="material-symbol text-[16px] text-secondary">engineering</span>
                <p className="text-[12px] text-secondary">
                  Orc[hestrator] v1.4 • Construído para organizar e orquestrar trabalho sem atrito
                </p>
              </div>
            </div>

            {/* Status row below the card */}
            <div className="mt-6 flex items-center justify-between px-2 text-[12px] font-semibold text-secondary-fixed-dim/70">
              <div className="flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full bg-[#56e5a9]" />
                <span>Fleet Status: Todos os agentes online</span>
              </div>
              <div className="flex items-center gap-3">
                <a className="transition-colors hover:text-on-surface" href="#">
                  Termos
                </a>
                <span>•</span>
                <a className="transition-colors hover:text-on-surface" href="#">
                  Suporte
                </a>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
