import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Pixel-pass tokens sampled from QuestFlow video frames (frame-001):
        // canvas ~#070B0A, surface ~#132320, mint brand #00E8B0, danger #FF5A5F.
        bg: "#070B0A",
        surface: "#0E1614",
        "surface-2": "#132320",
        "surface-3": "#1A2A26",
        border: "#1C2C28",
        "border-light": "#2A3F39",
        text: "#F2F4F8",
        muted: "#8FA8A0",
        "muted-2": "#5A6F68",
        primary: "#00E8B0",
        "primary-dim": "#0A2E26",
        danger: "#FF5A5F",
        "danger-dim": "#331A1C",
        accent: "#00C9A0",
        "accent-dim": "#0A2420",
        // M-VIS-02 / H-VIS-01: 35 files referenced `accent-bright` (the brighter
        // brand mint) and `rounded-pill` but neither token was defined, so those
        // utilities silently produced no style. Define them once here.
        "accent-bright": "#00E8B0",
        secondary: "#4B9EFF",
        "secondary-dim": "#14243D",
        up: "#00E8B0",
        down: "#FF5A5F",
        gold: "#F6C244",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        pill: "9999px",
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
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
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
        marquee: "marquee 60s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
