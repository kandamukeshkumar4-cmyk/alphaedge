import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // QuestFlow-terminal shell (docs/QUESTFLOW_DESIGN_SYSTEM.md): true
        // near-black canvas, neon signal green brand (#2DD4BF), agentic violet
        // accent (#14B8A6), cyan secondary. Green/red = YES/NO + up/down.
        bg: "#0C1210",
        surface: "#121A17",
        "surface-2": "#182220",
        "surface-3": "#1F2B27",
        border: "#243430",
        "border-light": "#32463F",
        text: "#F2F4F8",
        muted: "#9BB0A9",
        "muted-2": "#61756E",
        primary: "#2DD4BF",
        "primary-dim": "#12322C",
        danger: "#F1585C",
        "danger-dim": "#331A1C",
        accent: "#14B8A6",
        "accent-dim": "#0E2925",
        secondary: "#4B9EFF",
        "secondary-dim": "#14243D",
        up: "#2DD4BF",
        down: "#F1585C",
        gold: "#F6C244",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 2px 8px rgba(0,0,0,0.35)",
        lift: "0 8px 28px rgba(0,0,0,0.55)",
        glow: "0 0 0 1px rgba(20,184,166,0.4), 0 12px 32px rgba(20,184,166,0.18)",
        "glow-blue": "0 0 24px rgba(20,184,166,0.28)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "flash-green": {
          "0%": { backgroundColor: "rgba(45,212,191,0.0)" },
          "30%": { backgroundColor: "rgba(45,212,191,0.24)" },
          "100%": { backgroundColor: "rgba(45,212,191,0.0)" },
        },
        "flash-red": {
          "0%": { backgroundColor: "rgba(241,88,92,0.0)" },
          "30%": { backgroundColor: "rgba(241,88,92,0.24)" },
          "100%": { backgroundColor: "rgba(241,88,92,0.0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-468px 0" },
          "100%": { backgroundPosition: "468px 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.6", transform: "scale(1.12)" },
        },
        "ticker-in": {
          "0%": { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(110%)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s cubic-bezier(0.22,1,0.36,1) both",
        "flash-green": "flash-green 0.7s ease-out",
        "flash-red": "flash-red 0.7s ease-out",
        shimmer: "shimmer 1.4s linear infinite",
        "pulse-soft": "pulse-soft 1.8s ease-in-out infinite",
        "ticker-in": "ticker-in 0.4s ease-out both",
        "slide-in-right": "slide-in-right 0.35s cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
  plugins: [],
};
export default config;
