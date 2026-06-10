"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "alphaedge.onboarded";

export function useOnboarding() {
  const [shouldShow, setShouldShow] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        setShouldShow(true);
      }
    } catch {
      // localStorage unavailable (SSR or private mode)
    }
  }, []);

  function markDone() {
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // ignore
    }
    setShouldShow(false);
  }

  return { shouldShow, markDone };
}
