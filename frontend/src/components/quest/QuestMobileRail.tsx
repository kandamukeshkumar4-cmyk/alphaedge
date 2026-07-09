"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { QuestSignalRail } from "@/components/quest/QuestSignalRail";
import type { Market } from "@/lib/mock-data";

/** Mobile drawer for the Discover left rail (Top Traders / Trending / Signals). */
export function QuestMobileRail({ initialMarkets }: { initialMarkets?: Market[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-3 lg:hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-xl border border-border bg-surface px-3 py-2.5 text-sm font-bold text-text"
        aria-expanded={open}
      >
        <span>Live rails</span>
        <span className="text-xs font-semibold text-primary">{open ? "Hide" : "Show"}</span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="rail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className="mt-3 max-h-[50vh] overflow-y-auto rounded-xl border border-border bg-surface p-3">
              <QuestSignalRail initialMarkets={initialMarkets} />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
