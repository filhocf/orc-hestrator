import { NavLink, Outlet } from "react-router-dom";
import { NAV_SCREENS } from "@/nav";
import { useTheme } from "@/hooks/useTheme";

function Sidebar() {
  return (
    <aside className="flex w-sidebar shrink-0 flex-col border-r border-surface-border bg-surface-raised">
      <div className="flex h-topbar items-center gap-2.5 px-5">
        <img
          src="/mascote.png"
          alt="Orc[hestrator]"
          className="h-9 w-9 rounded-full object-cover"
        />
        <span className="font-display text-headline-sm text-content">
          Orc<span className="font-extrabold text-primary">[</span>hestrator
          <span className="font-extrabold text-primary">]</span>
        </span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
        {NAV_SCREENS.map((screen) => (
          <NavLink
            key={screen.path}
            to={screen.path}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-card px-3 py-2 text-body-md transition-colors",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-content-muted hover:bg-surface-overlay hover:text-content",
              ].join(" ")
            }
          >
            <span className="material-symbol text-[20px]">{screen.icon}</span>
            {screen.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

function Topbar() {
  const { theme, toggleTheme } = useTheme();
  return (
    <header className="flex h-topbar shrink-0 items-center gap-4 border-b border-surface-border bg-surface-raised px-6">
      <select
        aria-label="Selecionar workspace"
        className="rounded-card border border-surface-border bg-surface px-3 py-1.5 text-body-md text-content"
        defaultValue=""
      >
        <option value="">Todos os workspaces</option>
      </select>

      <label className="relative flex-1 max-w-md">
        <span className="material-symbol absolute left-3 top-1/2 -translate-y-1/2 text-[20px] text-content-subtle">
          search
        </span>
        <input
          type="search"
          placeholder="Buscar itens..."
          className="w-full rounded-pill border border-surface-border bg-surface py-1.5 pl-10 pr-4 text-body-md text-content placeholder:text-content-subtle focus:border-primary focus:outline-none"
        />
      </label>

      <div className="ml-auto flex items-center gap-3">
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"}
          className="flex h-9 w-9 items-center justify-center rounded-pill text-content-muted hover:bg-surface-overlay hover:text-content"
        >
          <span className="material-symbol text-[20px]">
            {theme === "dark" ? "light_mode" : "dark_mode"}
          </span>
        </button>
        <div
          className="flex h-9 w-9 items-center justify-center rounded-pill bg-primary font-display text-label-md text-primary-contrast"
          aria-label="Avatar do usuário"
        >
          Z
        </div>
      </div>
    </header>
  );
}

/** App shell: fixed sidebar + topbar, routed content in the main area. */
export default function Layout() {
  return (
    <div className="flex h-full w-full overflow-hidden bg-surface text-content">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
