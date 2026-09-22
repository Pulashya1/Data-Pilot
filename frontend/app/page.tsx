"use client";

import { ArrowRight, FlaskConical } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { SignalMeter } from "@/components/ui/signal-meter";
import { UploadDropzone } from "@/components/upload-dropzone";
import { ApiError, createSampleSession, listSamples, listSessions } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import type { SampleDataset, SessionSummary } from "@/types";

// The agent's actual route (backend/app/agent/graph.py), in the same visual language as the
// workspace's flight path, so a first-time user recognizes it once they're in a session.
const STEPS = [
  {
    title: "Profile",
    body: "Column types, missing values, and a data quality score, the moment the file lands.",
  },
  {
    title: "Confirm",
    body: "The agent proposes a target and an analysis plan. You approve or change both.",
  },
  {
    title: "Explore",
    body: "Each analysis runs as real notebook code in a sandbox. You decide on preprocessing and a baseline model.",
  },
  {
    title: "Export",
    body: "Download a notebook that reruns top to bottom, an HTML report, or the fitted pipeline.",
  },
];

function SamplePicker() {
  const router = useRouter();
  const [samples, setSamples] = useState<SampleDataset[] | null>(null);
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSamples()
      .then(setSamples)
      .catch(() => setSamples([]));
  }, []);

  const start = async (key: string) => {
    setLoadingKey(key);
    setError(null);
    try {
      const session = await createSampleSession(key);
      router.push(`/sessions/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the sample.");
      setLoadingKey(null);
    }
  };

  if (samples !== null && samples.length === 0) return null;

  return (
    <section aria-labelledby="samples-heading">
      <h2
        id="samples-heading"
        className="flex items-center gap-2 font-display text-base font-medium tracking-tight text-ink"
      >
        <FlaskConical size={15} className="text-accent" />
        No file handy? Try a sample
      </h2>
      <p className="mt-1 text-sm text-ink-tertiary">
        Small synthetic datasets, each built to show a different kind of problem.
      </p>
      {samples === null ? (
        <div className="py-6">
          <SignalMeter />
        </div>
      ) : (
        <ul className="mt-3 flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
          {samples.map((sample) => (
            <li key={sample.key}>
              <button
                type="button"
                onClick={() => void start(sample.key)}
                disabled={loadingKey !== null}
                className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2 disabled:cursor-wait disabled:opacity-60"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-ink">{sample.title}</span>
                  <span className="block text-xs leading-snug text-ink-tertiary">
                    {sample.description}
                  </span>
                </span>
                {loadingKey === sample.key ? (
                  <SignalMeter />
                ) : (
                  <ArrowRight
                    size={14}
                    className="shrink-0 text-ink-tertiary transition-colors group-hover:text-accent"
                  />
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="mt-2 text-sm text-critical" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function RecentSessions() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  useEffect(() => {
    listSessions()
      .then((all) => setSessions(all.slice(0, 3)))
      .catch(() => undefined);
  }, []);

  if (sessions.length === 0) return null;

  return (
    <section aria-labelledby="recent-heading">
      <div className="flex items-baseline justify-between">
        <h2
          id="recent-heading"
          className="font-display text-base font-medium tracking-tight text-ink"
        >
          Pick up where you left off
        </h2>
        <Link href="/sessions" className="text-xs text-ink-tertiary hover:text-accent">
          All sessions
        </Link>
      </div>
      <ul className="mt-3 flex flex-col gap-1">
        {sessions.map((s) => (
          <li key={s.id}>
            <Link
              href={`/sessions/${s.id}`}
              className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-surface-2"
            >
              <span className="truncate text-ink-secondary">{s.original_filename}</span>
              <span className="flex shrink-0 items-center gap-2 text-xs text-ink-tertiary">
                {s.agent_status === "waiting_decision" && (
                  <span className="text-warning">Needs you</span>
                )}
                {formatRelativeTime(s.created_at)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function HowItWorks() {
  return (
    <section aria-labelledby="how-heading" className="border-t border-line pt-10">
      <h2 id="how-heading" className="font-display text-base font-medium tracking-tight text-ink">
        How a session runs
      </h2>
      <ol className="mt-6 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-0">
        {STEPS.map((step, index) => (
          <li key={step.title} className="relative flex gap-3 lg:flex-col lg:pr-6">
            <div className="flex items-center lg:w-full" aria-hidden="true">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-accent font-display text-[11px] font-semibold text-accent">
                {index + 1}
              </span>
              {index < STEPS.length - 1 && (
                <span className="ml-2 hidden h-0.5 flex-1 bg-line-strong lg:block" />
              )}
            </div>
            <div>
              <h3 className="font-display text-sm font-semibold text-ink">{step.title}</h3>
              <p className="mt-1 max-w-[34ch] text-sm leading-relaxed text-ink-tertiary">
                {step.body}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function Home() {
  return (
    <AuthGuard>
      <main className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-10 lg:px-8 lg:py-14">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:gap-14">
          <div className="flex flex-col gap-6">
            <div>
              <h1 className="max-w-[18ch] font-display text-3xl font-semibold tracking-tight text-ink sm:text-[2.5rem] sm:leading-[1.1]">
                Explore a dataset with an agent that asks before it acts
              </h1>
              <p className="mt-4 max-w-[60ch] text-base leading-relaxed text-ink-secondary">
                DataPilot profiles your file, proposes a plan, and runs each analysis as real
                notebook code. It pauses for your call on the target, the plan, preprocessing, and
                the baseline model.
              </p>
            </div>
            <UploadDropzone />
          </div>
          <div className="flex flex-col gap-10 lg:pt-2">
            <RecentSessions />
            <SamplePicker />
          </div>
        </div>
        <HowItWorks />
      </main>
    </AuthGuard>
  );
}
