import CategoryDashboardClient from "./category-client";

// Server wrapper so this route works under `output: "export"` (static deploy):
// enumerate the app's known category taxonomy (the same lowercase API slugs the
// O02 endpoint recognises, plus the capitalized legacy values). The client
// component resolves the live per-category aggregate at runtime; an unknown
// category still renders an honest {found:false} state at runtime, and 404s on
// the static host.
export function generateStaticParams() {
  return [
    "sports",
    "politics",
    "crypto",
    "culture",
    "economics",
    "weather",
    "tech",
    "nfl",
    "NBA",
    "FIFA WC2026",
    "Elections",
  ].map((category) => ({ category }));
}

export default function CategoryDashboardPage() {
  return <CategoryDashboardClient />;
}
