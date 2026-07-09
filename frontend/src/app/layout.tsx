import type { Metadata } from "next";
import { Figtree, IBM_Plex_Mono } from "next/font/google";
import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import "@astryxdesign/theme-neutral/theme.css";
import "./globals.css";
import { Providers } from "./providers";
import { BottomNav } from "@/components/BottomNav";
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-bg font-sans text-text">
        <Providers>
          <AtlasPanelProvider>
            <ToastProvider>
              <HealthBanner />
              <SiteHeader />
              <PortfolioBanner />
              <div className="flex min-h-[calc(100vh-7rem)] w-full">
                <div className="min-w-0 flex-1 pb-20 lg:pb-0">{children}</div>
                <AtlasPanel />
              </div>
              <QuestLiveTicker />
              <BottomNav />
              <footer className="border-t border-border bg-surface/40 px-4 py-6 pb-24 text-center lg:pb-6">
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
