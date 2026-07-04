"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Theme } from "@astryxdesign/core/theme";
import { LinkProvider } from "@astryxdesign/core/Link";
import { neutralTheme } from "@astryxdesign/theme-neutral/built";

/**
 * Astryx (Meta's design system) provider. The neutral theme ships pre-built
 * CSS (imported in layout.tsx); brand tokens are overridden in globals.css
 * under [data-astryx-theme] to match the QuestFlow-terminal palette.
 * The app is dark-only, so the mode is pinned rather than following the OS.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <Theme theme={neutralTheme} mode="dark">
      <LinkProvider component={Link}>{children}</LinkProvider>
    </Theme>
  );
}
