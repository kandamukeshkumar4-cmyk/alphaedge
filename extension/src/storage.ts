export type ExtensionSettings = {
  token: string;
  apiBase: string;
};

const DEFAULT_API_BASE = "http://localhost:8000";

export function getSettings(): Promise<ExtensionSettings> {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      {
        token: "",
        apiBase: DEFAULT_API_BASE,
      },
      (items) => {
        resolve({
          token: String(items.token ?? ""),
          apiBase: normalizeApiBase(String(items.apiBase ?? DEFAULT_API_BASE)),
        });
      },
    );
  });
}

export function saveSettings(settings: Partial<ExtensionSettings>): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set(settings, () => resolve());
  });
}

export function normalizeApiBase(value: string): string {
  const normalized = value.trim().replace(/\/+$/, "");
  return normalized || DEFAULT_API_BASE;
}
