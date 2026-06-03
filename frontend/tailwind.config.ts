import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Kalshi-inspired market shell: green/red on deep charcoal.
        bg: "#090C0F",
        surface: "#0F1417",
        "surface-2": "#151B20",
        "surface-3": "#1D252B",
        border: "#243039",
        "border-light": "#33444D",
        text: "#F2F7F3",
        muted: "#9EA9A3",
        "muted-2": "#66716B",
        primary: "#24C66D",
        "primary-dim": "#0C2618",
        danger: "#FF4D4F",
        "danger-dim": "#2B1012",
        accent: "#58E28C",
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
        lift: "0 8px 28px rgba(0,0,0,0.5)",
        glow: "0 0 0 1px rgba(36,198,109,0.36), 0 12px 32px rgba(36,198,109,0.1)",
        "glow-blue": "0 0 24px rgba(36,198,109,0.22)",
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
