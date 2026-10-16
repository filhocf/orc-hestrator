# Orchestrator Control Hub — Frontend

Web UI for managing the Task Orchestrator. Decoupled React app that consumes the
Orc REST API. **Isolated** from the Python package (`src/task_orchestrator`): this
directory owns its own tooling, deps and build.

## Stack

- **Vite 6** + **React 18** + **TypeScript 5** (strict)
- **Tailwind CSS 3** (config-file tokens, `darkMode: 'class'`)
- **react-router-dom 6** (routing)
- **@tanstack/react-query 5** (server-state)
- **ESLint 9** (flat config)
- Fonts: Plus Jakarta Sans (display) + Inter (body) + Material Symbols Outlined (icons), via Google Fonts

## Run

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b + vite build → dist/
npm run preview  # serve the production build
npm run lint
```

## API wiring

- In dev, the Vite server proxies `/api` → `http://127.0.0.1:8005` (the Orc dev backend),
  so there's no CORS friction. Override the target with `VITE_API_PROXY_TARGET`.
- Override the API base entirely with `VITE_API_BASE` (e.g. point at a remote Orc).
  Defaults to `/api`. See `.env.example`.
- Typed client: `src/api/client.ts`. Types: `src/api/types.ts`.
- Errors: non-2xx responses (and structured `ToolError` bodies) throw a typed `ApiError`
  carrying `status`, `code` and optional `field`.

## Structure

```
frontend/
├── index.html              # fonts + root
├── tailwind.config.js      # design tokens (colors/fonts/type scale/radius)
├── vite.config.ts          # /api proxy + @ alias
├── public/
│   └── mascote.svg         # local logo/mascot (placeholder — see note below)
└── src/
    ├── main.tsx            # entry: Router + React Query providers
    ├── App.tsx             # routes (Login outside shell; 9 screens inside Layout)
    ├── nav.ts              # sidebar/nav single source of truth
    ├── index.css           # Tailwind layers + Material Symbols helper
    ├── api/
    │   ├── client.ts       # typed endpoint functions + ApiError
    │   └── types.ts        # WorkItem / Session / Claim / ... (from the backend model)
    ├── components/
    │   ├── Layout.tsx      # sidebar + topbar app shell
    │   └── Placeholder.tsx # temporary screen content
    ├── hooks/
    │   └── useTheme.ts     # light/dark toggle (class on <html>, persisted)
    └── pages/
        └── Login.tsx       # login screen (placeholder)
```

## Screens

Login, Visão geral, Time ao vivo, Board, Arcos, Grafo, Detalhe da tarefa (`/task/:id`),
Administração, Perfil. All but Login are routed placeholders today and will be
implemented one at a time.

## Notes / caveats

- **Design tokens**: the task referenced a Stitch design export (`DESIGN.md` + per-screen
  `code.html`) that was **not present** in the repo at scaffold time. The anchor colors
  named in the brief are honored exactly (`primary #ffc174`, `surface #031427`); the rest
  of the palette is a coherent set built around them. Reconcile with the Stitch export
  when it lands.
- **Mascot**: the official mascot PNG referenced in the brief was **not present** either.
  `public/mascote.svg` is a local placeholder — replace it with the official asset.
- **API shapes**: `src/api/types.ts` is derived from the authoritative backend data model
  (`src/task_orchestrator/db.py` + `engine/*`), because `docs/specs/SPEC-http-api.md` did
  not exist. The client assumes a `/api/*` JSON REST layer; today only a server-rendered
  HTML UI (`src/task_orchestrator/ui/app.py`) exists, so the REST layer must be added on
  the backend for the client to function end-to-end.
