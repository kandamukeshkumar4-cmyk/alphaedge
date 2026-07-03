import { QuestDiscover } from "@/components/quest/QuestDiscover";

// Home IS the Discover terminal — live markets grid, signal rails and the AI
// analyst dock. The full trading board lives at /markets.
export default function Home() {
  return (
    <main className="min-h-screen bg-bg">
      <QuestDiscover />
    </main>
  );
}
