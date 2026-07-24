import type { Metadata } from "next";

import { AlphaResearchPage } from "@/components/alpha/AlphaResearchPage";

/**
 * Loop 99 AU2 — /alpha research view. Multi-Factor Alpha: factor scores +
 * independent OOS validation for the canonical paper market, plus the
 * validated-factor report. Read-only research surface. Paper trading only.
 */
export const metadata: Metadata = {
  title: "Multi-Factor Alpha · AlphaEdge",
  description:
    "Paper-only factor research: seven signals scored per market, shown as edge only when they beat the closing line out-of-sample.",
};

export default function AlphaPage() {
  return <AlphaResearchPage />;
}
