"use client";

import { useEffect, useState } from "react";
import { SegTabs } from "@/components/ui/kit";
import { useAuth } from "@/hooks/useAuth";
import { apiHost } from "@/lib/api";

type ScannerInfo = {
  id: string;
  name: string;
  last_run_at: string;
};

type CombinedMarketInfo = {
  price: number | null;
  volume: number;
  lock_at: string | null;
};

type ConvergenceItem = {
  market_slug: string;
  market_title: string;
  scanner_count: number;
  scanners: ScannerInfo[];
  combined: CombinedMarketInfo;
};

type ConvergenceResponse = {
  items: ConvergenceItem[];
  scanner_total: number;
  computed_at: string;
};

type Scope = "mine" | "public";

export function ConvergencePanel() {
  const { token, isReady } = useAuth();
  const [scope, setScope] = useState<Scope>("public");
  const [data, setData] = useState<ConvergenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isReady) return;
    if (scope === "mine" && !token) {
      setError("Sign in required for 'mine' scope.");
      setData(null);
      return;
    }
    
    let dead = false;
    setLoading(true);
    setError(null);
    
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    fetch(`${apiHost}/api/v1/scanners/convergence?scope=${scope}&min_scanners=2`, { headers })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: ConvergenceResponse) => {
        if (!dead) setData(json);
      })
      .catch((err) => {
        if (!dead) setError(String(err));
      })
      .finally(() => {
        if (!dead) setLoading(false);
      });

    return () => {
      dead = true;
    };
  }, [token, isReady, scope]);

  return (
    <div className="mt-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-base font-black tracking-tight text-text sm:text-lg">Convergence</h2>
          <p className="mt-1 text-sm text-muted">Markets appearing in 2+ scanners</p>
        </div>
        <SegTabs
          value={scope}
          onChange={setScope}
          options={[
            { value: "public", label: "Public" },
            { value: "mine", label: "Mine" },
          ]}
        />
      </div>

      {loading ? (
        <div className="text-sm text-muted">Loading...</div>
      ) : error ? (
        <div className="text-sm text-red-500">{error}</div>
      ) : data ? (
        <div className="space-y-4">
          <p className="text-xs font-bold text-muted-2 uppercase tracking-wider">
            Total Scanners Evaluated: {data.scanner_total}
          </p>
          {data.items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface/40 p-6 text-center text-sm text-muted">
              No markets appear in 2 or more scanners.
            </div>
          ) : (
            <div className="grid gap-4">
              {data.items.map((item) => (
                <div key={item.market_slug} className="rounded-xl border border-border/60 bg-surface p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="font-bold text-text">{item.market_title}</h3>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-bold text-primary">
                      {item.scanner_count} scanners
                    </span>
                  </div>
                  <div className="text-xs text-muted">
                    Volume: ${item.combined.volume.toLocaleString()} | Price: {item.combined.price ?? "N/A"}
                  </div>
                  <div className="mt-3 border-t border-border/60 pt-3 text-xs text-muted-2">
                    Found in: {item.scanners.map((s) => s.name).join(", ")}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
