"use client";

import { ArrowRight, RadioTower } from "lucide-react";
import { useState } from "react";
import { ApiError, requestLoginLink } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [devLoginUrl, setDevLoginUrl] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setDetail(null);
    setDevLoginUrl(null);
    setIsSubmitting(true);
    try {
      const response = await requestLoginLink(email);
      setDetail(response.detail);
      setDevLoginUrl(response.dev_login_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send a sign-in link.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="grid-texture flex min-h-screen flex-col items-center justify-center gap-8 bg-canvas px-6 py-12">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-line bg-surface">
          <RadioTower size={20} className="text-accent" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">DataPilot</h1>
          <p className="mt-1.5 text-sm text-ink-tertiary">
            Sign in with a one-time email link — no password.
          </p>
        </div>
      </div>

      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="flex w-full max-w-sm flex-col gap-3 rounded-lg border border-line bg-surface p-5 shadow-floating"
      >
        <label htmlFor="email" className="text-xs font-medium text-ink-secondary">
          Email address
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="rounded-md border border-line-strong bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-ink-tertiary transition-colors focus:border-accent"
        />
        <button
          type="submit"
          disabled={isSubmitting || !email}
          className="mt-1 flex items-center justify-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-strong disabled:opacity-40"
        >
          {isSubmitting ? "Sending…" : "Send sign-in link"}
          {!isSubmitting && <ArrowRight size={14} />}
        </button>
      </form>

      {error && <p className="text-sm text-critical">{error}</p>}
      {detail && (
        <div className="flex w-full max-w-sm flex-col gap-2 rounded-md border border-line bg-surface-2 px-4 py-3 text-center">
          <p className="text-sm text-ink-secondary">{detail}</p>
          {devLoginUrl && (
            <a
              href={devLoginUrl}
              className="break-all font-mono text-xs text-accent underline decoration-accent/40 underline-offset-2 hover:text-accent-strong"
            >
              {devLoginUrl}
            </a>
          )}
        </div>
      )}

      <p className="max-w-sm text-center text-xs text-ink-tertiary">
        Data you upload may be sent to a third-party LLM provider for analysis. Prefer public or
        non-sensitive datasets.
      </p>
    </main>
  );
}
