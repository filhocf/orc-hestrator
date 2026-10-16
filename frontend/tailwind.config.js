/** @type {import('tailwindcss').Config} */
// Design tokens for the Orchestrator Control Hub.
//
// NOTE ON PROVENANCE: the task brief referenced a Stitch design export
// (docs/design/stitch/.../DESIGN.md + per-screen code.html) that is NOT present
// on this branch. The anchor colors explicitly named in the brief are honored
// exactly (primary #ffc174, surface #031427); the rest of the palette is a
// coherent set built around those anchors. When the Stitch export lands, verify
// and reconcile these values against it.
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Anchor tokens from the brief (exact).
        primary: {
          DEFAULT: "#ffc174",
          hover: "#ffb355",
          contrast: "#031427",
        },
        surface: {
          DEFAULT: "#031427", // deep navy canvas
          raised: "#0a2036", // cards / panels
          overlay: "#102b45", // hover / popovers
          border: "#1c3c5a",
        },
        // Secondary / tertiary accents derived around the anchors.
        tertiary: {
          DEFAULT: "#4fd1c5", // teal accent (links, active)
          hover: "#38b2ac",
        },
        content: {
          DEFAULT: "#e6eef6", // primary text on dark
          muted: "#9fb3c8", // secondary text
          subtle: "#64788f", // disabled / hints
        },
        // Status colors for work-item states.
        status: {
          queue: "#64788f",
          work: "#ffc174",
          review: "#a78bfa",
          done: "#4fd1c5",
          blocked: "#f87171",
          cancelled: "#52606d",
        },

        // --- Stitch MD3 tokens (exact, from docs/design/stitch export) ---
        // These mirror the Material Design 3 role names used verbatim in the
        // Stitch per-screen code.html mockups (login first). Added so screens
        // can be ported 1:1 with the exact classNames the designer produced.
        // Kept separate from the simplified scaffold palette above (which the
        // app shell / Layout depends on) to avoid regressing sibling screens.
        background: "#031427",
        "primary-container": "#f59e0b",
        "primary-fixed": "#ffddb8",
        "primary-fixed-dim": "#ffb95f",
        "on-primary": "#472a00",
        "on-primary-container": "#613b00",
        secondary: "#bec6e0",
        "secondary-container": "#3f465c",
        "secondary-fixed-dim": "#bec6e0",
        "on-surface": "#d3e4fe",
        "on-surface-variant": "#d8c3ad",
        "surface-variant": "#26364a",
        "surface-container-lowest": "#000f21",
        "surface-container-low": "#0b1c30",
        "surface-container": "#102034",
        "surface-container-high": "#1b2b3f",
        "surface-container-highest": "#26364a",
        "surface-bright": "#2a3a4f",
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        "headline-lg": ["2rem", { lineHeight: "2.5rem", fontWeight: "700" }],
        "headline-md": ["1.5rem", { lineHeight: "2rem", fontWeight: "700" }],
        "headline-sm": ["1.25rem", { lineHeight: "1.75rem", fontWeight: "600" }],
        "body-lg": ["1rem", { lineHeight: "1.5rem" }],
        "body-md": ["0.875rem", { lineHeight: "1.25rem" }],
        "body-sm": ["0.75rem", { lineHeight: "1rem" }],
        "label-lg": ["0.875rem", { lineHeight: "1.25rem", fontWeight: "600" }],
        "label-md": ["0.75rem", { lineHeight: "1rem", fontWeight: "600" }],
        "label-sm": ["0.6875rem", { lineHeight: "1rem", fontWeight: "600" }],
      },
      borderRadius: {
        card: "0.75rem",
        pill: "9999px",
      },
      spacing: {
        sidebar: "16rem",
        topbar: "4rem",
      },
    },
  },
  plugins: [],
};
