import type { Config } from "tailwindcss";

// Token source of truth: docs/design/DESIGN-quest.md (dark terminal canvas,
// green-tinted charcoal surfaces + mint accent). Token NAMES are stable so all
// pages inherit the retheme; only values changed from the old Coinbase palette.
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // All values are CSS variables (RGB triplets) defined in globals.css
        // — :root is the dark terminal palette, .light overrides for light mode.
        bg: "rgb(var(--c-bg) / <alpha-value>)",
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        "surface-2": "rgb(var(--c-surface-2) / <alpha-value>)",
        "surface-3": "rgb(var(--c-surface-3) / <alpha-value>)",
        border: "rgb(var(--c-border) / <alpha-value>)",
        "border-light": "rgb(var(--c-border-light) / <alpha-value>)",
        text: "rgb(var(--c-text) / <alpha-value>)",
        muted: "rgb(var(--c-muted) / <alpha-value>)",
        "muted-2": "rgb(var(--c-muted-2) / <alpha-value>)",
        primary: "rgb(var(--c-primary) / <alpha-value>)",
        "primary-dim": "rgb(var(--c-primary-dim) / <alpha-value>)",
        danger: "rgb(var(--c-danger) / <alpha-value>)",
        "danger-dim": "rgb(var(--c-danger-dim) / <alpha-value>)",
        accent: "rgb(var(--c-accent) / <alpha-value>)",
        "accent-active": "rgb(var(--c-accent-active) / <alpha-value>)",
        "accent-dim": "rgb(var(--c-accent-dim) / <alpha-value>)",
        "accent-bright": "rgb(var(--c-accent-bright) / <alpha-value>)",
        secondary: "rgb(var(--c-secondary) / <alpha-value>)",
        "secondary-dim": "rgb(var(--c-secondary-dim) / <alpha-value>)",
        up: "rgb(var(--c-primary) / <alpha-value>)",
        down: "rgb(var(--c-danger) / <alpha-value>)",
        gold: "rgb(var(--c-secondary) / <alpha-value>)",
      },
      borderRadius: {
        pill: "100px", // rounded.pill — every CTA
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        // Single shadow tier per design doc, dark-canvas equivalent.
        card: "0 4px 12px rgba(0,0,0,0.4)",
        lift: "0 8px 28px rgba(0,0,0,0.55)",
        glow: "0 0 0 1px rgba(32,201,151,0.4), 0 12px 32px rgba(32,201,151,0.16)",
        "glow-blue": "0 0 24px rgba(32,201,151,0.25)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "flash-green": {
          "0%": { backgroundColor: "rgba(5,177,105,0.0)" },
          "30%": { backgroundColor: "rgba(5,177,105,0.24)" },
          "100%": { backgroundColor: "rgba(5,177,105,0.0)" },
        },
        "flash-red": {
          "0%": { backgroundColor: "rgba(229,72,77,0.0)" },
          "30%": { backgroundColor: "rgba(229,72,77,0.24)" },
          "100%": { backgroundColor: "rgba(229,72,77,0.0)" },
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
        "price-flash-up": {
          "0%": { transform: "scale(1)" },
          "40%": { transform: "scale(1.08)" },
          "100%": { transform: "scale(1)" },
        },
        "price-flash-down": {
          "0%": { transform: "scale(1)" },
          "40%": { transform: "scale(0.94)" },
          "100%": { transform: "scale(1)" },
        },
        "xp-pop": {
          "0%": { opacity: "0", transform: "translateY(8px) scale(0.9)" },
          "20%": { opacity: "1", transform: "translateY(0) scale(1.05)" },
          "80%": { opacity: "1", transform: "translateY(-2px) scale(1)" },
          "100%": { opacity: "0", transform: "translateY(-14px) scale(0.95)" },
        },
        "streak-flame": {
          "0%, 100%": { transform: "scale(1) rotate(-2deg)" },
          "50%": { transform: "scale(1.15) rotate(2deg)" },
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
        "price-flash-up": "price-flash-up 0.45s ease-out",
        "price-flash-down": "price-flash-down 0.45s ease-out",
        "xp-pop": "xp-pop 1.6s cubic-bezier(0.22,1,0.36,1) both",
        "streak-flame": "streak-flame 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
