import { LibraryHub } from "@/components/library/LibraryHub";

/**
 * Loop V85 (L3) — /library hub. Unified cards across skills + scanners, tabs
 * All | Skills | Scanners | Subscribed, with Subscribe toggle + Fork. Paper
 * trading only.
 */
export default function LibraryPage() {
  return (
    <main className="min-h-screen bg-bg">
      <div className="mx-auto max-w-[1200px] px-4 py-8">
        <LibraryHub />
      </div>
    </main>
  );
}
