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
import { PortfolioBanner } from "@/components/PortfolioBanner";

// QuestFlow uses a rounded geometric sans; Figtree is the closest match.
// Kept on the --font-inter variable so tailwind config stays unchanged.
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
        <ToastProvider>
          <HealthBanner />
          <SiteHeader />
          <PortfolioBanner />
          <div className="min-h-[calc(100vh-7rem)] pb-20 lg:pb-0">{children}</div>
          <BottomNav />
          <footer className="border-t border-border bg-surface/40 px-4 py-6 pb-24 text-center lg:pb-6">
            <p className="mx-auto max-w-3xl text-xs leading-relaxed text-muted-2">
              {DISCLAIMER}
            </p>
          </footer>
        </ToastProvider>
        </Providers>
      </body>
    </html>
  );
}
