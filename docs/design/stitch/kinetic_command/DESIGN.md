---
name: Kinetic Command
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#554336'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#887364'
  outline-variant: '#dbc2b0'
  surface-tint: '#904d00'
  primary: '#8d4b00'
  on-primary: '#ffffff'
  primary-container: '#b15f00'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb77d'
  secondary: '#006e2d'
  on-secondary: '#ffffff'
  secondary-container: '#7cf994'
  on-secondary-container: '#007230'
  tertiary: '#712ae2'
  on-tertiary: '#ffffff'
  tertiary-container: '#8a4cfc'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdcc3'
  primary-fixed-dim: '#ffb77d'
  on-primary-fixed: '#2f1500'
  on-primary-fixed-variant: '#6e3900'
  secondary-fixed: '#7ffc97'
  secondary-fixed-dim: '#62df7d'
  on-secondary-fixed: '#002109'
  on-secondary-fixed-variant: '#005320'
  tertiary-fixed: '#eaddff'
  tertiary-fixed-dim: '#d2bbff'
  on-tertiary-fixed: '#25005a'
  on-tertiary-fixed-variant: '#5a00c6'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '800'
    lineHeight: 48px
    letterSpacing: -0.03em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '800'
    lineHeight: 38px
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.025em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  title-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.011em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: -0.006em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.04em
  mono-data:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-mobile: 0.75rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-base: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style

This design system sets the visual standard for an autonomous and human-in-the-loop operational nexus. Built for high-leverage decision environments, it merges the rigor of high-throughput industrial infrastructure with the clarity of state-of-the-art enterprise software. 

The aesthetic identity is **Modern Corporate & Precision Engineering**: ultra-luminous, pristine, high-density, and tactically grounded. The interface avoids frivolous ornamentation in favor of purposeful contrast, structural discipline, and immediate legibility. Crisp slate backdrops suspend stark white functional surfaces, framed by precision micro-borders and electrified with an alert, mechanical amber that signals vital energy and agency. 

Target users—system architects, autonomous swarm supervisors, and operations directors—require instant situational awareness. The emotional impression is commanding, vigilant, effortless, and unshakeable under load.

## Colors

The palette establishes an ultra-clean optical hierarchy optimized for prolonged command sessions and dense telemetry.

### Palette Hierarchy & Intent
- **Primary (Safety Amber / #D97706):** Represents intentional intervention, active computation, and mechanical warning. Reserved for high-value call-to-actions, primary state transitions, agent handoffs, and focused elements. Supporting shades: Light Accent (`#F59E0B`), Deep Accent (`#B45309`).
- **Secondary (Orc Green / #16A34A):** Designates verified autonomy, optimal latency, active agent heartbeats, and completed workflows. Accent shade: `#22C55E`.
- **Tertiary (Review Violet / #7C3AED):** Designates evaluation queues, human consensus loops, and deep-inspection thresholds.
- **Neutral (Slate Navy / #0F172A):** The typographic anchor. Anchors the structural geometry and data strings with absolute ink contrast against light backdrops.

### Canvas & Surface Architecture
- **Base Canvas:** `#F8FAFC` (Slate 50) for outer canvas framing, transitioning to `#F1F5F9` (Slate 100) for recessed control wells and tracking tracks.
- **Card & Surface Layers:** Pure `#FFFFFF` (White) to elevate active task clusters and metric blocks.
- **Borders & Dividers:** Subtle, structural delineation using `#E2E8F0` (Slate 200) for default boundaries and `#CBD5E1` (Slate 300) for interactive or active element borders.

### Semantic Status Tokens
- **Fila (Queued / Idle):** Slate Blue (`#64748B`)
- **Trabalhando (Processing / Active):** Amber (`#D97706`)
- **Revisão (Human Review / Blocked Approval):** Violet (`#7C3AED`)
- **Concluído (Resolved / Healthy):** Emerald (`#16A34A`)
- **Bloqueado (Critical Halt / System Alert):** Rose (`#E11D48`)

## Typography

The typographic hierarchy utilizes two synergistic typefaces: **Plus Jakarta Sans** for headlines and structural titles, pairing high-energy geometric personality with engineered authority; and **Inter** for dense tabular readouts, continuous agent body streams, and interactive control labels.

### Rules of Usage
- **Numerics & Agent Logs:** All real-time telemetry, node latencies, and process timers must activate tabular figures (`font-variant-numeric: tabular-nums`) to eliminate layout jitter during high-frequency data refresh.
- **Tracking & Contrast:** Large headlines enforce tight negative tracking (`-0.02em` to `-0.03em`) for a sharp editorial finish. Small tags and status badges use `label-sm` with expanded tracking (`+0.04em`) in uppercase to ensure rapid scanning during triage.
- **Hierarchy Tiers:** Primary values, KPIs, and card names leverage `#0F172A` (Slate 900). Secondary metadata, task context, and timestamps leverage `#334155` (Slate 700) or `#64748B` (Slate 500). Muted guidelines never fall below `#94A3B8` (Slate 400).

## Layout & Spacing

This design system uses a dense 8-point base grid system (with a precise 4-point micro-scale for nested agent parameters, pills, and indicators).

### Grid Configuration
- **Desktop (≥ 1280px):** 12-column dynamic fluid grid with fixed outer canvas padding (`margin-desktop: 2rem`) and `gutter-desktop: 1.5rem`. Multi-pane command decks span 3 columns for telemetry trees, 6 columns for active orchestration graphs/pipelines, and 3 columns for contextual inspector rails.
- **Tablet (768px – 1279px):** 8-column flexible grid with `margin-tablet: 1.5rem` and `gutter: 1rem`. Sidebars collapse to drawer overlays or compact icon strips (64px width).
- **Mobile (< 768px):** 4-column column-stacked grid with `margin: 1rem` and `gutter-mobile: 0.75rem`. Complex pipeline canvases transition into linear chronological streams with horizontal swipe tabs.

### Spatial Rhythm
Compact components (badges, input fields, and metric tokens) rely on `space-xs` (4px) and `space-sm` (8px). Structural surfaces, panel inner gutters, and modular card bodies enforce `space-base` (16px) or `space-lg` (24px) to preserve breathing room amid data density.

## Elevation & Depth

Visual hierarchy is maintained via crisp **low-contrast micro-outlines paired with subtle, ambient daylight shadows**. Avoid heavy drop shadows or dark overlays; depth in this system mimics precision architectural acrylic layers resting atop clean slate fixtures.

### Elevation Levels
- **Level 0 (Floor/Canvas):** `#F8FAFC`. Completely flat. Used for backdrop containers, viewport margins, and horizontal rule anchors.
- **Level 1 (Structural Cards / Working Panels):** Pure `#FFFFFF`. Surface is defined by a crisp perimeter border `1px solid #E2E8F0` and an ambient shadow: `0px 1px 3px 0px rgba(15, 23, 42, 0.05), 0px 1px 2px -1px rgba(15, 23, 42, 0.03)`.
- **Level 2 (Hover State / Interactive Cards / Dropdowns):** Pure `#FFFFFF`. Enhanced perimeter border `1px solid #CBD5E1` and buoyant elevation shadow: `0px 4px 6px -1px rgba(15, 23, 42, 0.07), 0px 2px 4px -2px rgba(15, 23, 42, 0.05)`.
- **Level 3 (Modals / Inspector Drawers / Flyout Menus):** Pure `#FFFFFF`. Border: `1px solid #E2E8F0` accompanied by an expansive contextual shadow: `0px 20px 25px -5px rgba(15, 23, 42, 0.08), 0px 8px 10px -6px rgba(15, 23, 42, 0.04)`.
- **Level 4 (Critical Halts & Urgent Callouts):** Elevated modal layered with an ambient tinted perimeter glow: `0px 0px 0px 3px rgba(225, 29, 72, 0.15)`.

## Shapes

The interface expresses a modern, crisp dashboard geometry governed by standard `0.5rem` (8px) corner radials.

### Corner Radii Definitions
- **Micro Radius (4px / 0.25rem):** Applied to badges, inline tags, micro-action icons, segmented control segments, and form checkbox controls.
- **Default System Radius (8px / 0.5rem - `rounded-lg`):** The primary signature shape. Applied to interactive buttons, text input fields, operational cards, data grids, tooltips, and contextual dropdown menus.
- **Structural Radius (12px / 0.75rem - `rounded-xl`):** Applied to primary command center panels, dashboard widgets, and main modal dialogue frames.
- **Full Radius (9999px):** Applied strictly to system pulse pips, avatar portraits, and circular connection ports on node canvases.

## Components

### Buttons
- **Primary:** Background `#D97706` (Safety Amber), text `#FFFFFF`, font-weight 600, border: `1px solid #B45309`. Hover: background `#B45309`. Active: transform scale `0.98`. Focus ring: `2px solid #FFFFFF`, `2px solid #F59E0B`.
- **Secondary / Ghost:** Background `#FFFFFF`, text `#0F172A`, border `1px solid #E2E8F0`. Hover: background `#F8FAFC`, border `#CBD5E1`.
- **Destructive:** Background `#FFF1F2`, text `#E11D48`, border `1px solid #FECDD3`. Hover: background `#FFE4E6`.

### Status Badges & Chips
- Status indicators combine a solid 6px circular indicator pip with contextual badge text (Inter `label-sm`).
- **Fila:** Background `#F1F5F9`, border `#E2E8F0`, text `#475569`, pip `#64748B`.
- **Trabalhando:** Background `#FEF3C7`, border `#FDE68A`, text `#92400E`, pip `#D97706` with subtle CSS pulse animation.
- **Revisão:** Background `#F5F3FF`, border `#DDD6FE`, text `#5B21B6`, pip `#7C3AED`.
- **Concluído:** Background `#F0FDF4`, border `#BBF7D0`, text `#166534`, pip `#16A34A`.
- **Bloqueado:** Background `#FFF1F2`, border `#FECDD3`, text `#9F1239`, pip `#E11D48`.

### Input Fields & Controls
- **Text Inputs:** Height 40px, background `#FFFFFF`, border `1px solid #CBD5E1`, text `#0F172A`, placeholder `#94A3B8`, border-radius 8px. Hover: border `#94A3B8`. Focus: border `#D97706`, box-shadow `0px 0px 0px 3px rgba(217, 119, 6, 0.15)`.
- **Checkboxes & Radios:** Size 18px. Active check fill `#D97706` with white vector checkmark. Radios employ standard circular concentric rings.

### Orchestration Cards & Task Containers
- Base background `#FFFFFF`, border `1px solid #E2E8F0`, border-radius 8px, padding 16px. Top accent border line (2px height) dynamically colored by the active process state (e.g., `#16A34A` for operational health, `#D97706` for ongoing calculation).
- Header row hosts the node identifier (Inter `mono-data`), task label (Plus Jakarta Sans `title-sm`), and right-aligned status chip.

### Telemetry / Node Rails
- Monospace-styled execution readouts set inside `#F8FAFC` recessed pods with `1px solid #E2E8F0`. Visual flow connectors (DAG nodes) utilize a continuous 2px line in `#CBD5E1` transitioning to `#16A34A` upon live packet validation.