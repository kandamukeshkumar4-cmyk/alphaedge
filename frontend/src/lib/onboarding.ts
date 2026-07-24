export const ONBOARDING_STORAGE_KEY = "ae_onboarded_v1";

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function isFirstRun(): boolean {
  const storage = getStorage();
  if (!storage) return false;

  try {
    return storage.getItem(ONBOARDING_STORAGE_KEY) !== "true";
  } catch {
    return false;
  }
}

export function markOnboarded(): void {
  const storage = getStorage();
  if (!storage) return;

  try {
    storage.setItem(ONBOARDING_STORAGE_KEY, "true");
  } catch {
    // Storage can be unavailable in private browsing or with blocked cookies.
  }
}

export function resetOnboarding(): void {
  const storage = getStorage();
  if (!storage) return;

  try {
    storage.removeItem(ONBOARDING_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in private browsing or with blocked cookies.
  }
}
