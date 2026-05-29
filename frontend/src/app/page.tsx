import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-bold">AlphaEdge</h1>
      <p className="mt-2 text-slate-400">Paper-trading NBA prediction market simulation</p>
      <nav className="mt-8 flex gap-4">
        <Link href="/admin" className="rounded bg-indigo-600 px-4 py-2 text-sm">
          Admin
        </Link>
        <Link href="/eval" className="rounded border border-slate-700 px-4 py-2 text-sm">
          Proof Dashboard
        </Link>
        <Link href="/markets" className="rounded border border-slate-700 px-4 py-2 text-sm">
          Markets
        </Link>
      </nav>
    </main>
  );
}
