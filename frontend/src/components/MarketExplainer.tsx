"use client";
import { useState } from "react";

interface Props { slug: string; }

export default function MarketExplainer({ slug }: Props) {
  const [open, setOpen] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    if (explanation || loading) return;
    setLoading(true);
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/v1/markets/${slug}/explain`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setExplanation(d?.explanation ?? "AI insight unavailable."))
      .catch(() => setExplanation("AI insight unavailable."))
      .finally(() => setLoading(false));
  };

  return (
    <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-700">
      <button
        onClick={() => { setOpen(!open); if (!open) load(); }}
        className="w-full flex items-center justify-between px-4 py-2 text-sm font-medium text-left text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg"
      >
        <span>AI Insight</span>
        <span>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 text-sm text-gray-600 dark:text-gray-400">
          {loading ? "Loading AI insight…" : explanation}
        </div>
      )}
    </div>
  );
}
