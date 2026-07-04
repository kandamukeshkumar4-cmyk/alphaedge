// Weather edge desk API client. Degrades to empty when the backend is down.
import { API_BASE } from "./alphaedge-api";

export type WeatherBucket = {
  ticker: string;
  bucket: string;
  model_probability: number;
  market_yes: number | null;
  edge: number | null;
  read: "yes-underpriced" | "yes-overpriced" | null;
};

export type WeatherCityReport = {
  city: string;
  series_ticker: string;
  date: string;
  forecast_high_f: number;
  sigma_f: number;
  source: string;
  buckets: WeatherBucket[];
};

export type WeatherEdges = {
  date: string;
  cities: WeatherCityReport[];
  cached: boolean;
};

export async function fetchWeatherEdges(date?: string): Promise<WeatherEdges | null> {
  if (!API_BASE) return null;
  try {
    const qs = date ? `?date=${encodeURIComponent(date)}` : "";
    const res = await fetch(`${API_BASE}/api/v1/weather/edges${qs}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as WeatherEdges;
  } catch {
    return null;
  }
}
