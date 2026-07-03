// Macro desk API client (E11). Degrades to empty when the backend is down.
import { API_BASE } from "./alphaedge-api";

export type MacroIndicator = {
  key: string;
  label: string;
  unit: string;
  value: number;
  prev_value: number | null;
  change: number | null;
  date: string;
  source: string;
};

export type MacroDashboard = {
  indicators: MacroIndicator[];
  source: string;
  updated_at: number;
};

export async function fetchMacro(): Promise<MacroDashboard | null> {
  if (!API_BASE) return null;
  try {
    const res = await fetch(`${API_BASE}/api/v1/macro`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as MacroDashboard;
  } catch {
    return null;
  }
}
