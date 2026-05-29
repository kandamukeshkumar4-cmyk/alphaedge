import type { Metadata } from "next";
import "./globals.css";

const DISCLAIMER =
  "This project is a paper-trading simulation for research and portfolio demonstration only. No real-money trading, betting, or settlement is supported.";

export const metadata: Metadata = {
  title: "AlphaEdge — Paper Trading Dashboard",
  description: DISCLAIMER,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <footer className="border-t border-slate-800 p-4 text-center text-xs text-slate-500">
          {DISCLAIMER}
        </footer>
      </body>
    </html>
  );
}
