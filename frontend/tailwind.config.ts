import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // QuestFlow-terminal shell (docs/QUESTFLOW_DESIGN_SYSTEM.md): true
        // near-black canvas, neon signal green brand (#00E28A), agentic violet
        // accent (#7C5CFF), cyan secondary. Green/red = YES/NO + up/down.
        bg: "#060709",
        surface: "#0C0E12",
        "surface-2": "#12151B",
        "surface-3": "#1A1E26",
        border: "#1D222C",
        "border-light": "#2C323E",
        text: "#F2F4F8",
        muted: "#97A0B2",
        "muted-2": "#5E6779",
        primary: "#00E28A",
        "primary-dim": "#04281B",
        danger: "#FF4D5E",
        "danger-dim": "#2C0F14",
        accent: "#7C5CFF",
        "accent-dim": "#191234",
        secondary: "#22D3EE",
        "secondary-dim": "#0A2530",
        up: "#00E28A",
        down: "#FF4D5E",
        gold: "#F6C244",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 2px 8px rgba(0,0,0,0.35)",
        lift: "0 8px 28px rgba(0,0,0,0.55)",
        glow: "0 0 0 1px rgba(124,92,255,0.4), 0 12px 32px rgba(124,92,255,0.18)",
        "glow-blue": "0 0 24px rgba(124,92,255,0.28)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "flash-green": {
          "0%": { backgroundColor: "rgba(0,226,138,0.0)" },
          "30%": { backgroundColor: "rgba(0,226,138,0.24)" },
          "100%": { backgroundColor: "rgba(0,226,138,0.0)" },
        },
        "flash-red": {
          "0%": { backgroundColor: "rgba(255,77,94,0.0)" },
          "30%": { backgroundColor: "rgba(255,77,94,0.24)" },
          "100%": { backgroundColor: "rgba(255,77,94,0.0)" },
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
