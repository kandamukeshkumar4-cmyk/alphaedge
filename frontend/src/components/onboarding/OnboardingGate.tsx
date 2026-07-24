"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { isFirstRun } from "@/lib/onboarding";

import { OnboardingTour } from "./OnboardingTour";

export function OnboardingGate() {
  const pathname = usePathname();
  const [showTour, setShowTour] = useState(false);

  useEffect(() => {
    if (pathname.startsWith("/onboarding")) return;
    setShowTour(isFirstRun());
  }, [pathname]);

  if (!showTour || pathname.startsWith("/onboarding")) return null;

  return <OnboardingTour onComplete={() => setShowTour(false)} />;
}
