export const ADMIN_API_KEY_STORAGE = "alphaedge.adminApiKey";

export function readAdminApiKey(): string {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    return localStorage.getItem(ADMIN_API_KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

export function writeAdminApiKey(key: string): void {
  try {
    localStorage.setItem(ADMIN_API_KEY_STORAGE, key);
  } catch {
    // localStorage unavailable
  }
}

export function adminHeaders(apiKey: string): HeadersInit {
  return {
    "X-Admin-API-Key": apiKey,
  };
}
