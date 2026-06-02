import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { ToastProvider } from "@/components/ToastProvider";

const inter = Inter({
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
        <ToastProvider>
          <SiteHeader />
          <div className="min-h-[calc(100vh-7rem)]">{children}</div>
          <footer className="border-t border-border bg-surface/40 px-4 py-6 text-center">
            <p className="mx-auto max-w-3xl text-xs leading-relaxed text-muted-2">
              {DISCLAIMER}
            </p>
          </footer>
        </ToastProvider>
      </body>
    </html>
  );
}
