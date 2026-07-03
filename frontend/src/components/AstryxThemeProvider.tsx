"use client";

import { Theme } from "@astryxdesign/core/theme";
import { neutralTheme } from "@/styles/theme/neutralTheme";

export function AstryxThemeProvider({ children }: { children: React.ReactNode }) {
  return <Theme theme={neutralTheme}>{children}</Theme>;
}
