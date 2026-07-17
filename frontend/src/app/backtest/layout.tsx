import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Backtest",
  description: "Walk-forward paper backtests with Brier and flat-stake research metrics.",
  path: "/backtest",
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
