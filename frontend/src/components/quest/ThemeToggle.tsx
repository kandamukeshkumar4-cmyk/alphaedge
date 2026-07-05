"use client";

import { useEffect, useState } from "react";

// Toggles the `.light` class on <html>, which flips the CSS-variable palette in
// globals.css (:root = dark terminal, .light = light). Persisted to localStorage;
// a small inline script in layout.tsx applies the saved choice before first paint.
export function ThemeToggle() {
  const [light, setLight] = useState(false);

  useEffect(() => {
    setLight(document.documentElement.classList.contains("light"));
  }, []);

  const toggle = () => {
    const next = !light;
    document.documentElement.classList.toggle("light", next);
    try {
      localStorage.setItem("ae_theme", next ? "light" : "dark");
    } catch {
      /* private mode */
    }
    setLight(next);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      className="grid h-7 w-7 place-items-center rounded-lg text-muted transition hover:bg-surface hover:text-text"
      aria-label={light ? "Switch to dark theme" : "Switch to light theme"}
      title={light ? "Switch to dark theme" : "Switch to light theme"}
    >
      {light ? (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="4" />
          <path
            d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
            strokeLinecap="round"
          />
        </svg>
      )}
    </button>
  );
}
