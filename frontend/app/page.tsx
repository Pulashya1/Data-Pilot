import { HealthStatus } from "@/components/health-status";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-24">
      <h1 className="text-3xl font-semibold">DataPilot</h1>
      <p className="text-neutral-600">Agentic EDA & feature engineering assistant.</p>
      <HealthStatus />
    </main>
  );
}
