"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

type Market = { slug: string; title: string; status: string };

export default function MarketsPage() {
  const [markets, setMarkets] = useState<Market[]>([]);

  useEffect(() => {
    if (!API) {
      return;
    }

    fetch(`${API}/api/v1/markets`)
      .then((r) => r.json())
      .then(setMarkets)
      .catch(() => setMarkets([]));
  }, []);

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-bold">Markets</h1>
      <ul className="mt-6 space-y-2">
        {markets.map((m) => (
          <li key={m.slug} className="rounded border border-slate-800 p-3 text-sm">
            <span className="font-medium">{m.title}</span> — {m.slug} ({m.status})
          </li>
        ))}
        {!markets.length && (
          <li className="text-slate-500">No markets — seed Lakers vs Celtics via admin API.</li>
        )}
      </ul>
    </main>
  );
}
