import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { UploadDropzone } from "@/components/upload-dropzone";

export default function Home() {
  return (
    <AuthGuard>
      <main className="grid-texture flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center gap-8 px-6 py-16">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">
            Upload a dataset
          </h1>
          <p className="max-w-md text-sm leading-relaxed text-ink-tertiary">
            An agent explores it with you — profiling, feature engineering, and a live notebook,
            step by step.
          </p>
        </div>
        <UploadDropzone />
        <Link
          href="/sessions"
          className="flex items-center gap-1 text-sm text-ink-tertiary transition-colors hover:text-accent"
        >
          View past sessions
          <ArrowRight size={13} />
        </Link>
      </main>
    </AuthGuard>
  );
}
