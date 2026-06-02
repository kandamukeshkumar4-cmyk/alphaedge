import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Red / Blue / Black palette
        bg: "#08080C",
        surface: "#121219",
        "surface-2": "#1A1A24",
        "surface-3": "#23232F",
        border: "#242430",
        "border-light": "#33334A",
        text: "#F4F6FB",
        muted: "#939AAC",
        "muted-2": "#5C6273",
        primary: "#2F6BFF", // blue — YES / Buy / brand
        "primary-dim": "#0E1A33",
        danger: "#FF3B47", // red — NO / Sell
        "danger-dim": "#2A0E13",
        accent: "#4D8DFF", // lighter blue — hover / links / focus
        up: "#2F6BFF", // blue candle
        down: "#FF3B47", // red candle
        gold: "#FFB020",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 2px 8px rgba(0,0,0,0.35)",
        lift: "0 8px 28px rgba(0,0,0,0.5)",
        glow: "0 0 0 1px rgba(77,141,255,0.45), 0 8px 28px rgba(47,107,255,0.1)",
        "glow-blue": "0 0 24px rgba(47,107,255,0.28)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "flash-green": {
          "0%": { backgroundColor: "rgba(47,107,255,0.0)" },
          "30%": { backgroundColor: "rgba(47,107,255,0.24)" },
          "100%": { backgroundColor: "rgba(47,107,255,0.0)" },
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
