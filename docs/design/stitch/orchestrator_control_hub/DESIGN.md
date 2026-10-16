---
name: Orchestrator Control Hub
colors:
  surface: '#031427'
  surface-dim: '#031427'
  surface-bright: '#2a3a4f'
  surface-container-lowest: '#000f21'
  surface-container-low: '#0b1c30'
  surface-container: '#102034'
  surface-container-high: '#1b2b3f'
  surface-container-highest: '#26364a'
  on-surface: '#d3e4fe'
  on-surface-variant: '#d8c3ad'
  inverse-surface: '#d3e4fe'
  inverse-on-surface: '#213145'
  outline: '#a08e7a'
  outline-variant: '#534434'
  surface-tint: '#ffb95f'
  primary: '#ffc174'
  on-primary: '#472a00'
  primary-container: '#f59e0b'
  on-primary-container: '#613b00'
  inverse-primary: '#855300'
  secondary: '#bec6e0'
  on-secondary: '#283044'
  secondary-container: '#3f465c'
  on-secondary-container: '#adb4ce'
  tertiary: '#56e5a9'
  on-tertiary: '#003824'
  tertiary-container: '#30c88f'
  on-tertiary-container: '#004e34'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffddb8'
  primary-fixed-dim: '#ffb95f'
  on-primary-fixed: '#2a1700'
  on-primary-fixed-variant: '#653e00'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#031427'
  on-background: '#d3e4fe'
  surface-variant: '#26364a'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 44px
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '800'
    lineHeight: 36px
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 30px
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-sm: 1rem
  margin: 2rem
  margin-sm: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

The design system establishes a high-trust, optimistic mission-control aesthetic for human managers coordinating hybrid fleets of AI agents and human contributors. Rooted in the visual narrative of an industrious, cheerful orc donning a safety helmet, the interface balances industrial utility with friendly accessibility. 

### Visual Identity & Philosophy
- **Approachable Pragmatism**: Complex multi-agent workflows, queue depths, and token allocations are rendered with clarity, removing intimidating devops jargon in favor of clear status metaphors.
- **Tactile Construction Utility**: Inspired by architectural dashboards and safety infrastructure, the interface employs crisp containment boundaries, high-contrast indicators, and amber accents that demand attention without triggering panic.
- **Tone of Voice (pt-BR)**: Action-oriented, cooperative, and direct. Microcopy emphasizes collaborative execution (e.g., "Em andamento", "Aguardando revisão", "Pausar esteira", "Delegar tarefa").

### Design Style Archetype
A blend of **Modern Enterprise Utility** and **Warm Tactile Minimalism**:
- Generous internal padding balanced by compact, scannable data layouts.
- Structured card containment using subtle perimeter strokes rather than murky elevation.
- Purposeful status-based iconography, pill badges, and dynamic progress trackers that render complex orchestration visually comprehensible at a glance.

## Colors

The palette grounds high-density control operations using deep slate foundations paired with high-visibility safety amber and semantic status indicators.

### Roles & Semantic Distribution
- **Safety Amber (Primary)**: `#F59E0B` (Base), `#FBBF24` (Hover/Active), `#D97706` (Border/Focus). Denotes primary actions, operational triggers, orchestration status, and active selection states.
- **Industrial Slate / Navy (Secondary / Dark Surfaces)**:
  - Deep Base (`#0B0F19` / `#0F172A`): Root dashboard canvas and navigation shell.
  - Layer 1 Container (`#1E293B`): Card surfaces, telemetry panels, table containers.
  - Layer 2 Container (`#334155`): Hover surfaces, nested cards, popovers, active tabs.
- **Semantic Fleet Status**:
  - **Online / Executando (Emerald)**: `#10B981` (Surface: `rgba(16, 185, 129, 0.12)`, Border: `#059669`).
  - **Aguardando / Em Revisão (Amber)**: `#F59E0B` (Surface: `rgba(245, 158, 11, 0.12)`, Border: `#D97706`).
  - **Bloqueado / Erro (Rose)**: `#F43F5E` (Surface: `rgba(244, 63, 94, 0.12)`, Border: `#E11D48`).
  - **Em Espera / Fila (Slate)**: `#64748B` (Surface: `rgba(100, 116, 139, 0.12)`, Border: `#475569`).

### Light Mode Adaptability
In light mode contexts:
- Canvas shifts to `#F8FAFC`, cards to `#FFFFFF`, and borders to `#E2E8F0`.
- Amber deepens to `#D97706` for interactive elements to guarantee WCAG AAA contrast against light backgrounds.
- High-contrast text uses `#0F172A` for primary headlines and `#475569` for body copy.

## Typography

The typographic hierarchy couples **Plus Jakarta Sans** for structural, friendly, and geometric headlines with **Inter** for dense tabular data, code feeds, labels, and analytical metrics.

### Typographic Rules
- **Numerical Metric Readouts**: Dashboard stat counters (e.g., token usage, agent completion percentages) use `Plus Jakarta Sans` with `tabular-nums` enabled to avoid visual jitter during live updates.
- **Portuguese Diacritics**: Both typefaces natively support pt-BR glyphs (`ç`, `ã`, `õ`, `ê`, `á`) without vertical clipping across all line-height configurations.
- **Labels & Micro-Badges**: `label-sm` is uppercase with `letter-spacing: 0.05em` when paired with operational state indicators (e.g., `EM FILA`, `EXECUTANDO`, `REVISÃO`).

## Layout & Spacing

The control center implements a multi-tier dashboard layout based on an adaptive 12-column fluid grid.

### Layout Model
- **Desktop (>= 1280px)**: 12-column grid. Left persistent sidebar (280px fixed width), main dashboard workspace fluid with 24px (`1.5rem`) gutters and 32px (`2rem`) canvas margin. Right contextual inspector panel collapsible (360px).
- **Tablet (768px - 1279px)**: 8-column grid. Sidebar compresses into an icon rail (72px), canvas margins reduce to 20px, inspector converts to an overlay slide-out panel.
- **Mobile (< 768px)**: 4-column single-column flow with 16px (`1rem`) horizontal margin. Global navigation collapses to a top bar with a slide-over sheet. Grid layouts stack vertically; data tables convert to summary cards.

### Spacing Principles
- Component internal paddings scale systematically: `space-xs` (4px) for pill tags, `space-sm` (8px) for buttons and inputs, `space-md` (16px) for inner card containers, `space-lg` (24px) for section splits, and `space-xl` (40px) for high-level module segregation.

## Elevation & Depth

To sustain a crisp, technical aesthetic suitable for rapid data digestion, depth is produced through layered tonal tiers and crisp boundary strokes rather than diffuse, heavy drop shadows.

### Layer Hierarchy
1. **Canvas Tier (Lowest)**: `#0F172A` (Dark) / `#F8FAFC` (Light). Hosts page backgrounds and grid lines.
2. **Structural Tier (Cards / Panels)**: `#1E293B` (Dark) / `#FFFFFF` (Light). Outlined with 1px border `#334155` (Dark) / `#E2E8F0` (Light). No shadow in resting state.
3. **Elevated Interactive Tier (Modals / Drawers / Tooltips)**: `#1E293B` with 1px border `#475569` and a focused ambient shadow: `0 12px 32px -4px rgba(0, 0, 0, 0.45)`.
4. **Active Element Illumination**: Focused inputs and activated agent nodes utilize an amber glow: `0 0 0 3px rgba(245, 158, 11, 0.25)`.

## Shapes

The design system adopts a roundedness factor of `2` (`0.5rem` / `8px` default radius), balancing industrial precision with approachable warmth.

### Corner Curvature Scale
- **Small Controls (`rounded`, 8px)**: Buttons, text fields, dropdown trigger buttons, tag badges.
- **Structural Containers (`rounded-lg`, 16px)**: Agent cards, task execution panels, metric charts, workflow nodes.
- **Overlays (`rounded-xl`, 24px)**: Slide-over panels, prompt dialogs, modal windows.
- **Indicators (`rounded-full`)**: Agent status dots, avatar containers, numeric pill counters.

## Components

### Buttons
- **Primary ("Ação Principal")**: Safety amber background (`#F59E0B`), dark slate text (`#0F172A`), font weight 600. Hover: `#FBBF24`. Pressed: `#D97706`. Height: 40px (desktop), 44px (mobile).
- **Secondary ("Ação Secundária")**: Transparent background with 1px border (`#475569`), light text (`#F8FAFC`). Hover: `#334155` background.
- **Destructive ("Interromper / Abortar")**: Rose background (`rgba(244, 63, 94, 0.15)`), rose border (`#F43F5E`), rose text (`#FDA4AF`). Hover: `#F43F5E` with `#FFFFFF` text.

### Chips & Badges
- Compact indicators (height: 24px, radius: 9999px, padding: 0 10px).
- Pair an 8px circular status dot on the left with high-contrast text:
  - `Executando`: Emerald dot (`#10B981`) + emerald text tint.
  - `Revisão Humana`: Amber dot (`#F59E0B`) + amber text tint.
  - `Bloqueado`: Rose dot (`#F43F5E`) + rose text tint.
  - `Na Fila`: Slate dot (`#94A3B8`) + slate text tint.

### Inputs & Form Controls
- Dark background (`#0F172A`), 1px border (`#334155`), text (`#F8FAFC`), placeholder (`#64748B`).
- On focus: border shifts to `#F59E0B` with an ambient amber focus ring (`box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2)`).
- Checkboxes and radios use a 20px strike target with amber fill on checked state and sharp SVG iconography.

### Cards & Fleet Panels
- Enclosed with 1px border (`#334155`) over `#1E293B`.
- Header section houses agent/human identity, role indicator (e.g., "Agente de Triagem", "Revisor Humano"), and status badge.
- Body displays current task description, live progress bar with amber fill, and resource usage metric tags.
- Footer features quick action triggers: "Inspecionar", "Pausar", "Reatribuir".

### Specialized Orchestration Components
- **Agent Workstream Row**: Compact visual queue showing step-by-step progress with segmented breadcrumb bars.
- **Mascot Callout (Orc Banner)**: A warm informational callout box with a subtle amber border and a warm avatar avatar slot, used for system tips, delegation suggestions, and operational handoff confirmations.