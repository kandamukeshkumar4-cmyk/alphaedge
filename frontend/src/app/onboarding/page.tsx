"use client";

import { useEffect, useState } from "react";

import { OnboardingTour } from "@/components/onboarding/OnboardingTour";
import { resetOnboarding } from "@/lib/onboarding";

export default function OnboardingPage() {
  const [showTour, setShowTour] = useState(false);

  useEffect(() => {
    resetOnboarding();
    setShowTour(true);
  }, []);

  if (!showTour) return null;

  return <OnboardingTour onComplete={() => setShowTour(false)} />;
}
