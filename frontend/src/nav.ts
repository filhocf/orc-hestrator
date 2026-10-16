// Single source of truth for the app's navigable screens.
// Each screen is a routed placeholder for now; real screens land one at a time.
export interface NavScreen {
  path: string;
  label: string;
  icon: string; // Material Symbols Outlined name
  /** When true, the item is only shown to users with role "admin" (UX gate;
   *  the REAL authorization is enforced by the backend). */
  adminOnly?: boolean;
}

export const NAV_SCREENS: NavScreen[] = [
  { path: "/overview", label: "Visão geral", icon: "dashboard" },
  { path: "/live", label: "Time ao vivo", icon: "groups" },
  { path: "/board", label: "Board", icon: "view_kanban" },
  { path: "/arcs", label: "Arcos", icon: "account_tree" },
  { path: "/graph", label: "Grafo", icon: "hub" },
  { path: "/admin", label: "Administração", icon: "settings", adminOnly: true },
  { path: "/profile", label: "Perfil", icon: "person" },
];
