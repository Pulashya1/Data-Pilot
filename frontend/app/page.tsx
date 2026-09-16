import Link from "next/link";
import { UploadDropzone } from "@/components/upload-dropzone";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8 text-center">
      <div>
        <h1 className="text-3xl font-semibold">DataPilot</h1>
        <p className="mt-1 text-neutral-600">
          Upload a dataset and get an agentic EDA & feature engineering assistant.
        </p>
      </div>
      <UploadDropzone />
      <Link href="/sessions" className="text-sm text-neutral-500 underline hover:text-neutral-900">
        View past sessions
      </Link>
    </main>
  );
}
