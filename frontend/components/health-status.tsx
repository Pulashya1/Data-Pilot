"use client";

import { useEffect, useState } from "react";
import { fetchHealth, type HealthResponse } from "@/lib/api";

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unknown error"));
  }, []);

  if (error) {
    return <p className="text-sm text-red-500">Backend unreachable: {error}</p>;
  }

  if (!health) {
    return <p className="text-sm text-neutral-500">Checking backend status…</p>;
  }

  return (
    <p className="text-sm text-neutral-500">
      Backend: {health.status} · LLM model: {health.llm.model}
    </p>
  );
}
