import type { Metadata } from "next";
import Link from "next/link";
import { Figtree, IBM_Plex_Mono } from "next/font/google";
import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import "@astryxdesign/theme-neutral/theme.css";
import "./globals.css";
import { Providers } from "./providers";
import { BottomNav } from "@/components/BottomNav";
import { FirstBetOnboarding } from "@/components/FirstBetOnboarding";
import { HealthBanner } from "@/components/HealthBanner";
import { SiteHeader } from "@/components/SiteHeader";
import { ToastProvider } from "@/components/ToastProvider";
import { QuestLiveTicker } from "@/components/quest/QuestLiveTicker";
import { PortfolioBanner } from "@/components/PortfolioBanner";
import { AtlasPanel } from "@/components/quest/AtlasPanel";
import { AtlasPanelProvider } from "@/context/atlas-panel";

// QuestFlow uses a rounded geometric sans; Figtree is the closest match.
const inter = Figtree({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono",
  display: "swap",
});

const DISCLAIMER =
  "AlphaEdge is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only.";

export const metadata: Metadata = {
  title: "AlphaEdge — AI Prediction Markets",
  description: DISCLAIMER,
};

/** Dark-only paper terminal — no light chrome / theme toggle (PC08). */
export const viewport = {
  colorScheme: "dark" as const,
  themeColor: "#070B0A",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`} style={{ colorScheme: "dark" }}>
      <body className="min-h-screen bg-bg font-sans text-text">
        <Providers>
          <AtlasPanelProvider>
            <ToastProvider>
              {/* M-A11Y-01: skip past the header/nav straight to the page. */}
              <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-[100] focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-bold focus:text-bg"
              >
                Skip to main content
              </a>
              <HealthBanner />
              <SiteHeader />
              <PortfolioBanner />
              <div className="flex min-h-[calc(100vh-7rem)] w-full">
                <div id="main-content" tabIndex={-1} className="min-w-0 flex-1 pb-20 lg:pb-0">
                  {children}
                </div>
                <AtlasPanel />
              </div>
              <QuestLiveTicker />
              <FirstBetOnboarding />
              <BottomNav />
              <footer className="border-t border-border bg-surface/40 px-4 py-6 pb-24 text-center lg:pb-6">
                <nav className="mb-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs font-semibold">
                  <Link href="/features" className="text-muted transition hover:text-primary">
                    Feature map
                  </Link>
                  <Link href="/markets" className="text-muted transition hover:text-primary">
                    Markets
                  </Link>
                  <Link href="/eval" className="text-muted transition hover:text-primary">
                    Proof
                  </Link>
                  <Link href="/pods" className="text-muted transition hover:text-primary">
                    Pods
                  </Link>
                  <Link href="/portfolio" className="text-muted transition hover:text-primary">
                    Portfolio
                  </Link>
                </nav>
                <p className="mx-auto max-w-3xl text-xs leading-relaxed text-muted-2">
                  {DISCLAIMER}
                </p>
              </footer>
            </ToastProvider>
          </AtlasPanelProvider>
        </Providers>
      </body>
    </html>
  );
}
