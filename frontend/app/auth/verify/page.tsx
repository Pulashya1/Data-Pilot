"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { SignalMeter } from "@/components/ui/signal-meter";
import { ApiError, verifyLoginToken } from "@/lib/api";

function VerifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("This sign-in link is missing its token.");
      return;
    }
    verifyLoginToken(token)
      .then(() => router.replace("/sessions"))
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "This sign-in link is invalid."),
      );
  }, [token, router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-canvas p-8 text-center">
      {error ? (
        <>
          <p className="text-sm text-critical">{error}</p>
          <a
            href="/login"
            className="text-sm text-accent underline decoration-accent/40 underline-offset-2 hover:text-accent-strong"
          >
            Back to sign in
          </a>
        </>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <SignalMeter />
          <p className="text-sm text-ink-tertiary">Signing you in…</p>
        </div>
      )}
    </main>
  );
}

export default function VerifyPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-canvas">
          <SignalMeter />
        </main>
      }
    >
      <VerifyContent />
    </Suspense>
  );
}
