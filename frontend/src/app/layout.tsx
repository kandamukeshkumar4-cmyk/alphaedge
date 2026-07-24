import type { Metadata } from "next";
import Link from "next/link";
import { Figtree, IBM_Plex_Mono } from "next/font/google";
import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import "@astryxdesign/theme-neutral/theme.css";
import "./globals.css";
import { Providers } from "./providers";
import { BottomNav } from "@/components/BottomNav";
import { CoachMarks } from "@/components/CoachMarks";
import { FirstBetOnboarding } from "@/components/FirstBetOnboarding";
import { HealthBanner } from "@/components/HealthBanner";
import { SiteHeader } from "@/components/SiteHeader";
import { ToastProvider } from "@/components/ToastProvider";
import { QuestLiveTicker } from "@/components/quest/QuestLiveTicker";
import { PortfolioBanner } from "@/components/PortfolioBanner";
import { AtlasPanel } from "@/components/quest/AtlasPanel";
import { AtlasPanelProvider } from "@/context/atlas-panel";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";
import {
  DEFAULT_DESCRIPTION,
  DEFAULT_TITLE,
  SITE_NAME,
  SITE_URL,
} from "@/lib/site-metadata";

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

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: DEFAULT_TITLE,
    template: `%s — ${SITE_NAME}`,
  },
  description: DEFAULT_DESCRIPTION,
  applicationName: SITE_NAME,
  // Loop 103 P1 — installability via app/manifest.ts → /manifest.webmanifest
  manifest: "/manifest.webmanifest",
  keywords: [
    "paper trading",
    "prediction markets",
    "sports",
    "elections",
    "Brier score",
    "calibration",
    "AlphaEdge",
    "AI research desk",
    "simulated funds",
  ],
  authors: [{ name: SITE_NAME }],
  creator: SITE_NAME,
  alternates: {
    canonical: SITE_URL,
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
  // Exact paper-trading disclaimer also appears in the footer body.
  other: {
    "paper-trading-disclaimer": PAPER_TRADING_DISCLAIMER,
  },
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
          <OnboardingGate />
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
              <CoachMarks />
              <BottomNav />
              <footer className="border-t border-border bg-surface/40 px-4 py-6 pb-24 text-center lg:pb-6">
                <nav
                  aria-label="Site footer"
                  className="mb-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs font-semibold"
                >
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
                  <Link href="/about" className="text-muted transition hover:text-primary">
                    About
                  </Link>
                  <Link href="/terms" className="text-muted transition hover:text-primary">
                    Terms
                  </Link>
                </nav>
                <p className="mx-auto max-w-3xl text-xs leading-relaxed text-muted-2">
                  {PAPER_TRADING_DISCLAIMER}
                </p>
              </footer>
            </ToastProvider>
          </AtlasPanelProvider>
        </Providers>
      </body>
    </html>
  );
}
