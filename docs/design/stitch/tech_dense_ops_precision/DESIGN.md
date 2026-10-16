---
name: Tech Dense / Ops Precision
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#bcc9cd'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#869397'
  outline-variant: '#3d494c'
  surface-tint: '#4cd7f6'
  primary: '#4cd7f6'
  on-primary: '#003640'
  primary-container: '#06b6d4'
  on-primary-container: '#00424f'
  inverse-primary: '#00687a'
  secondary: '#4edea3'
  on-secondary: '#003824'
  secondary-container: '#00a572'
  on-secondary-container: '#00311f'
  tertiary: '#ffb95f'
  on-tertiary: '#472a00'
  tertiary-container: '#e79400'
  on-tertiary-container: '#563400'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#acedff'
  primary-fixed-dim: '#4cd7f6'
  on-primary-fixed: '#001f26'
  on-primary-fixed-variant: '#004e5c'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.5rem
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: '600'
    lineHeight: 1.25rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '600'
    lineHeight: 1.125rem
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.125rem
    letterSpacing: -0.005em
  body-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1rem
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '500'
    lineHeight: 1rem
    letterSpacing: -0.01em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.6875rem
    fontWeight: '500'
    lineHeight: 0.875rem
    letterSpacing: 0em
  code-dense:
    fontFamily: JetBrains Mono
    fontSize: 0.6875rem
    fontWeight: '400'
    lineHeight: 0.875rem
    letterSpacing: 0.01em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.5rem
  margin: 0.75rem
  space-xs: 0.125rem
  space-sm: 0.25rem
  space-md: 0.5rem
  space-lg: 0.75rem
  space-xl: 1rem
---

## Brand & Style

The design system embodies deep technical mastery, low-latency execution, and extreme operational clarity. Crafted for infrastructure operators, distributed systems engineers, and autonomous agent supervisors, the UI operates as a cockpit rather than a traditional canvas: dense, authoritative, and strictly utilitarian.

The visual style merges high-density keyboard-first UX with precise computational aesthetics. It discards decorative bloat in favor of 1px hairline dividers, structured data telemetry, and hyper-legible status indicators. The environment feels immediate, zero-latency, and perpetually synchronized.

## Colors

The palette is engineered around an ultra-deep slate and carbon matrix calibrated for prolonged terminal-grade immersion without visual fatigue.

### Surface Architecture
- **Canvas Base (`#07090e`)**: Deep abyss background reserved for root viewport canvasing.
- **Surface (`#0b0f17`)**: Base application workspace layer and pinned side-nav docks.
- **Container Low (`#111622`)**: Data tables, inactive panel sectors, and grouped section canvases.
- **Container (`#171d2b`)**: Default card containers, floating toolbars, and input wells.
- **Container High (`#1e2638`)**: Active selections, hovering rows, and contextual popover sheets.

### Structural Hairlines
- **Subtle Hairline (`#232b3e`)**: Standard 1px boundary between adjacent dense cells and layout panes.
- **Active / Structural Hairline (`#2e384d`)**: Focus rings, panel splitters, and modal enclosures.

### Operational Telemetry Accents
- **Cyan (`#06b6d4`)**: gRPC streams, telemetry packets, primary command actions, and real-time I/O transfers.
- **Emerald (`#10b981`)**: Active agent consensus, healthy daemon nodes, and completed runs.
- **Amber (`#f59e0b` / `#d97706`)**: Throttle limits, non-blocking drift, and safety overrides.
- **Crimson (`#ef4444`)**: Uncaught trace exceptions, deadlock nodes, and fatal interruptions.
- **Purple (`#a855f7`)**: Escalations requiring human judgment and policy signatures.

## Typography

Typography prioritizes information density and computational rhythm. 

- **Primary Sans (Inter)**: Handles layout titles, panel labels, and narrative descriptions with geometric clarity and tight letter tracking.
- **Monospaced Engine (JetBrains Mono)**: Mandatory for entity identifiers (`#TSK-810`), millisecond latency indicators, memory addresses, agent identifiers (`host/agent/session`), and hotkey badges. Tabular figures (`tnum`) must remain strictly active across all numeric counters to eliminate horizontal layout jitter during streaming updates.

## Layout & Spacing

Layout geometry relies on a compact fluid modular grid system optimized for multi-pane viewports, telemetry split-screens, and ultra-dense data grids.

- **Spacing Increments**: Uses a strict 4px sub-scale (2px micro-gap, 4px compact, 8px standard, 12px panel gap, 16px sector separation). Large breathing spaces are prohibited; every pixel conveys operational status or structural alignment.
- **Screen Distribution**:
  - **Desktop / Multi-Monitor**: Pinned master-detail sidebars with variable-width sliding drawer monitors. Pane gutters stay pinned to `0.5rem` (`8px`) to maximize data density.
  - **Tablet / Laptop**: Multi-column grids compress into stacked collapsible accordion streams.
  - **Mobile**: Single-column vertical stream; peripheral telemetry docks convert into modal bottom-sheets triggered via floating gesture chips.

## Elevation & Depth

Visual depth is produced strictly through structural background tonal layers and razor-sharp 1px hairline borders rather than volumetric or soft diffused shadows.

- **Layer Tiering**: Elements elevate by stepping up the neutral palette: `#07090e` (Base) → `#0b0f17` (Canvas) → `#111622` (Panel) → `#171d2b` (Floating Element / Popover) → `#1e2638` (Hover / Active).
- **Outlines Over Shadows**: Drop shadows are eliminated across standard views. Instead, interactive floating elements (e.g., Command Palette, Dropdown Menus) employ an internal 1px border (`#2e384d`) paired with a minimal dark grounding shadow: `0 8px 16px -4px rgba(0, 0, 0, 0.75)`.
- **Focus Rings**: Non-blurred, high-precision dual hairline borders: `0 0 0 1px #07090e, 0 0 0 2px #06b6d4`.

## Shapes

The interface employs a disciplined, subtle corner rounding (`0.25rem` / `4px`) designed to feel crisp, structural, and architectural. Full pill geometries are strictly forbidden with the sole exception of status ping dots. Rectilinear boundaries reinforce the tool’s machine-precision personality.

## Components

### Buttons & Action Bars
- **Height**: Fixed at `24px` (dense) or `28px` (default).
- **Styling**: `#171d2b` base, 1px `#232b3e` border, 4px radius, horizontal padding of `8px`. Text set in `Inter` Medium (`12px`).
- **Interactive State**: Hover advances surface to `#1e2638` and border to `#2e384d`. Active states introduce an immediate 0.5px inset snap.

### Micro-Badges & Telemetry Chips
- **Geometry**: Compact height of `18px`, padding `0 4px`, font `JetBrains Mono` (`11px`).
- **Styling**: Monochromatic or status-tinted background at 10% opacity with a corresponding solid 1px hairline border at 30% opacity (e.g., Cyan `#06b6d41a` bg with `#06b6d44d` border).

### Keyboard Shortcut Indicators (KBDs)
- **Geometry**: Height `16px`, min-width `16px`, border-radius `2px`, padding `0 3px`.
- **Appearance**: `#111622` fill, 1px `#2e384d` outline, typography set to `JetBrains Mono` (`10px`), neutral text (`#94a3b8`).

### Status Dots & Signal Beacons
- **Geometry**: Static `6px` circle.
- **Pulsing State**: Active agents render a solid `6px` emerald center dot paired with an ambient non-blurring ring expanding to `10px` at 40% opacity.

### Data Tables & Stream Rows
- **Metrics**: Row height locked to `28px` for ultra-density.
- **Dividers**: 1px horizontal rule using `#232b3e`.
- **Row Interaction**: Hover triggers an instantaneous background transition to `#111622` without layout shift. Focus displays a 2px vertical accent bar on the left edge.

### Inputs & Terminal Fields
- **Height**: `26px`, inset padding `4px 8px`.
- **Colors**: Canvas `#0b0f17`, hairline `#232b3e`, focusing to `#06b6d4`. Monospaced text entry for parameters, keys, and queries.