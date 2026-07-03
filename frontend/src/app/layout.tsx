import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import "./globals.css";
import { AstryxThemeProvider } from "@/components/AstryxThemeProvider";
import { HealthBanner } from "@/components/HealthBanner";
import { QuestHeader } from "@/components/quest/QuestHeader";
import { QuestOnboarding } from "@/components/quest/QuestOnboarding";
import { ToastProvider } from "@/components/ToastProvider";
import { GamificationLayer } from "@/components/GamificationLayer";
import { GamificationProvider } from "@/lib/gamification";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

// CoinbaseMono substitute per docs/design/DESIGN-coinbase.md — JetBrains Mono 500.
const mono = JetBrains_Mono({
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
        {/* Apply the saved theme before paint to avoid a flash of the wrong one. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{if(localStorage.getItem('ae_theme')==='light')document.documentElement.classList.add('light')}catch(e){}",
          }}
        />
        <AstryxThemeProvider>
          <GamificationProvider>
            <ToastProvider>
              <HealthBanner />
              <QuestHeader />
              <div className="min-h-[calc(100vh-7rem)]">{children}</div>
              <footer className="border-t border-border bg-bg px-4 py-6 text-center">
                <p className="mx-auto max-w-3xl text-xs leading-relaxed text-muted-2">
                  {DISCLAIMER}
                </p>
              </footer>
              <GamificationLayer />
              <QuestOnboarding />
            </ToastProvider>
          </GamificationProvider>
        </AstryxThemeProvider>
      </body>
    </html>
  );
}
