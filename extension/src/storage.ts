export type ExtensionSettings = {
  token: string;
  apiBase: string;
  dashboardUrl: string;
};

const DEFAULT_API_BASE = "http://localhost:8000";
const DEFAULT_DASHBOARD_URL = "http://localhost:3000/forecast";

export function getSettings(): Promise<ExtensionSettings> {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      {
        token: "",
        apiBase: DEFAULT_API_BASE,
        dashboardUrl: DEFAULT_DASHBOARD_URL,
      },
      (items) => {
        resolve({
          token: String(items.token ?? ""),
          apiBase: normalizeApiBase(String(items.apiBase ?? DEFAULT_API_BASE)),
          dashboardUrl: normalizeUrl(String(items.dashboardUrl ?? DEFAULT_DASHBOARD_URL)),
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

export function normalizeUrl(value: string): string {
  const normalized = value.trim();
  return normalized || DEFAULT_DASHBOARD_URL;
}
