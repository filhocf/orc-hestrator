import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/auth/context";

/**
 * Perfil e configurações — screen 9.
 * Ported from the Stitch mockup intent:
 *   docs/design/stitch/perfil_e_configura_es_orc_hestrator/code.html
 *
 * HONESTY CONTRACT — what is REAL vs. visual-only:
 *
 *   REAL / functional:
 *     - Logged user     -> useAuth() (server session via getMe(), F2)
 *     - Theme toggle     -> src/hooks/useTheme.ts (light/dark, persisted, toggles
 *                           the `dark` class on <html>) — same hook the topbar uses
 *     - Sair (logout)    -> useAuth().logout() (POST /api/auth/logout) + navigate("/login")
 *
 *   VISUAL ONLY (marked "em breve" / não funcional):
 *     - Language selection: there is NO i18n yet; only pt-BR is wired. The select
 *       is shown for the future but does not change any strings.
 *     - Theme VARIANT (e.g. "Zen"): the app has a single theme palette; variants
 *       are shown disabled until palettes land.
 *     - Notifications / account editing: no backend endpoints — placeholders.
 *
 * TODO: i18n + theme palettes + account API = futuro.
 */

function initials(name: string | null): string {
  if (!name) return "?";
  const clean = name.replace(/[^a-zA-Z0-9]/g, "");
  return (clean.slice(0, 1).toUpperCase() || "?");
}

/** Small "não funcional" / future marker pill. */
function SoonTag({ children = "Em breve" }: { children?: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary-container/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary-container">
      <span className="material-symbol text-[12px]" style={{ fontVariationSettings: "'FILL' 1" }}>
        schedule
      </span>
      {children}
    </span>
  );
}

function Card({
  icon,
  title,
  subtitle,
  badge,
  children,
}: {
  icon: string;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl bg-surface-container-low p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="material-symbol mt-0.5 text-[22px] text-primary">{icon}</span>
        <div className="flex flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-title-md text-on-surface">{title}</h2>
            {badge}
          </div>
          {subtitle && <p className="text-body-sm text-on-surface-variant">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

// --- Theme segmented control (REAL) ---------------------------------------

function ThemeControl() {
  const { theme, toggleTheme } = useTheme();
  const options: { value: "light" | "dark"; label: string; icon: string }[] = [
    { value: "light", label: "Claro", icon: "light_mode" },
    { value: "dark", label: "Escuro", icon: "dark_mode" },
  ];
  return (
    <div className="inline-flex rounded-xl bg-surface-container-high p-1" role="group" aria-label="Tema">
      {options.map((opt) => {
        const active = theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            aria-pressed={active}
            onClick={() => {
              if (!active) toggleTheme();
            }}
            className={[
              "flex items-center gap-2 rounded-lg px-4 py-2 text-label-md font-semibold transition-colors",
              active
                ? "bg-primary text-primary-contrast shadow-sm"
                : "text-on-surface-variant hover:text-on-surface",
            ].join(" ")}
          >
            <span className="material-symbol text-[18px]">{opt.icon}</span>
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// --- Page -----------------------------------------------------------------

export default function Profile() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const username = user?.username ?? null;
  // Language is visual-only (no i18n yet) — kept in local state so the select
  // is interactive, but it does NOT change any app strings.
  const [language, setLanguage] = useState("pt-BR");

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-headline-md text-on-surface">Perfil e configurações</h1>
        <p className="text-body-md text-on-surface-variant">
          Sua conta, aparência e preferências do Orc.
        </p>
      </header>

      {/* Account — REAL logged user (server session, F2) */}
      <Card icon="account_circle" title="Conta">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary font-display text-headline-sm text-primary-contrast">
            {initials(username)}
          </div>
          <div className="flex flex-col">
            <span className="font-display text-title-md text-on-surface">
              {username ?? "Usuário não identificado"}
            </span>
            <span className="text-body-sm text-on-surface-variant">
              {user?.role === "admin"
                ? "Administrador"
                : user
                  ? `Perfil: ${user.role}`
                  : "Sessão não identificada"}
            </span>
          </div>
        </div>
      </Card>

      {/* Appearance — REAL theme toggle + visual-only variant */}
      <Card
        icon="palette"
        title="Aparência"
        subtitle="O tema é aplicado em toda a interface e fica salvo neste navegador."
      >
        <div className="flex flex-col gap-2">
          <span className="text-label-sm font-semibold uppercase tracking-wide text-on-surface-variant">
            Tema
          </span>
          <ThemeControl />
        </div>

        {/* Theme VARIANT — visual only (single palette for now). */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-label-sm font-semibold uppercase tracking-wide text-on-surface-variant">
              Variante
            </span>
            <SoonTag />
          </div>
          <div className="inline-flex rounded-xl bg-surface-container-high p-1 opacity-60">
            {["Padrão", "Zen"].map((v, i) => (
              <button
                key={v}
                type="button"
                disabled
                aria-disabled="true"
                title="Variantes de tema chegam no futuro"
                className={[
                  "cursor-not-allowed rounded-lg px-4 py-2 text-label-md font-semibold",
                  i === 0 ? "bg-primary/40 text-on-surface" : "text-on-surface-variant",
                ].join(" ")}
              >
                {v}
              </button>
            ))}
          </div>
          <p className="text-body-sm text-on-surface-variant/80">
            Apenas a paleta padrão está disponível. Variantes serão habilitadas no futuro.
          </p>
        </div>
      </Card>

      {/* Language — visual only (no i18n yet) */}
      <Card icon="translate" title="Idioma" badge={<SoonTag>Apenas pt-BR</SoonTag>}>
        <div className="flex flex-col gap-2">
          <label htmlFor="language" className="sr-only">
            Idioma
          </label>
          <select
            id="language"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="max-w-xs rounded-xl border border-surface-border bg-surface px-3 py-2 text-body-md text-content"
          >
            <option value="pt-BR">Português (Brasil)</option>
            <option value="en-US" disabled>
              English (em breve)
            </option>
            <option value="es-ES" disabled>
              Español (em breve)
            </option>
          </select>
          <p className="text-body-sm text-on-surface-variant/80">
            A interface ainda não tem internacionalização (i18n). Esta seleção é apenas visual — só
            pt-BR está ativo.
          </p>
        </div>
      </Card>

      {/* Session — REAL logout */}
      <Card icon="logout" title="Sessão">
        <button
          type="button"
          onClick={handleLogout}
          className="inline-flex w-fit items-center gap-2 rounded-xl bg-status-blocked/15 px-4 py-2.5 text-label-md font-semibold text-status-blocked transition-colors hover:bg-status-blocked/25"
        >
          <span className="material-symbol text-[18px]">logout</span>
          Sair
        </button>
        <p className="text-body-sm text-on-surface-variant/80">
          Encerra a sessão no servidor e volta para a tela de login.
        </p>
      </Card>
    </div>
  );
}
