import { ImageResponse } from "next/og";

export const dynamic = "force-static";
export const alt = "AlphaEdge — paper-trading prediction markets";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** Same branded card as opengraph-image (duplicated so Next can see the route config). */
export default function TwitterImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#070B0A",
          color: "#E8F5F1",
          padding: "64px 72px",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            color: "#2DD4BF",
            fontSize: 28,
            fontWeight: 700,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          <div
            style={{
              width: 14,
              height: 14,
              borderRadius: 999,
              background: "#2DD4BF",
              boxShadow: "0 0 18px rgba(45,212,191,0.85)",
            }}
          />
          AlphaEdge
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div
            style={{
              fontSize: 64,
              fontWeight: 900,
              lineHeight: 1.05,
              letterSpacing: "-0.03em",
              maxWidth: 900,
            }}
          >
            Paper-trading prediction markets
          </div>
          <div
            style={{
              fontSize: 28,
              lineHeight: 1.35,
              color: "#9BB5AD",
              maxWidth: 880,
            }}
          >
            Simulated funds for research and portfolio demonstration only. Not
            financial advice. No real-money execution.
          </div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            color: "#6F8B82",
            fontSize: 22,
            fontWeight: 600,
          }}
        >
          <span>Markets · Forecasts · Proof</span>
          <span>PAPER TRADING ONLY</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
