import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // vidIQ-inspired shell: cool near-black navy + bright blue brand accent
        // (#2E7DF6) and coral secondary. Green/red reserved for YES/NO + up/down.
        bg: "#0A0C12",
        surface: "#12141C",
        "surface-2": "#181B26",
        "surface-3": "#222636",
        border: "#232838",
        "border-light": "#353B4F",
        text: "#EEF1F7",
        muted: "#9AA3B5",
        "muted-2": "#646C7E",
        primary: "#24C66D",
        "primary-dim": "#0C2618",
        danger: "#FF4D4F",
        "danger-dim": "#2B1012",
        accent: "#2E7DF6",
        "accent-dim": "#0E1F3D",
        secondary: "#FF4D8D",
        "secondary-dim": "#2A1020",
        up: "#24C66D",
        down: "#FF4D4F",
        gold: "#F6A524",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 2px 8px rgba(0,0,0,0.35)",
        lift: "0 8px 28px rgba(0,0,0,0.55)",
        glow: "0 0 0 1px rgba(46,125,246,0.4), 0 12px 32px rgba(46,125,246,0.18)",
        "glow-blue": "0 0 24px rgba(46,125,246,0.28)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "flash-green": {
          "0%": { backgroundColor: "rgba(36,198,109,0.0)" },
          "30%": { backgroundColor: "rgba(36,198,109,0.24)" },
          "100%": { backgroundColor: "rgba(36,198,109,0.0)" },
        },
        "flash-red": {
          "0%": { backgroundColor: "rgba(255,59,71,0.0)" },
          "30%": { backgroundColor: "rgba(255,59,71,0.24)" },
          "100%": { backgroundColor: "rgba(255,59,71,0.0)" },
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
