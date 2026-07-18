"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { uploadSong, validateAudioFile } from "./lib/api";

const STEPS = [
  { title: "Upload a song", body: "We split it into instrumental and reference vocal tracks." },
  { title: "Sing along", body: "Get a 3-2-1 countdown, then sing over the instrumental." },
  { title: "See your score", body: "Pitch, tone, and lyrics accuracy, plus a timeline breakdown." },
];

export default function Home() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const validationError = validateAudioFile(file);
    if (validationError) {
      setError(validationError);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const { song_id } = await uploadSong(file);
      router.push(`/song/${song_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-10 bg-zinc-50 px-6 py-16 dark:bg-black">
      <div className="flex flex-col items-center gap-3 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Singing Similarity Scorer
        </h1>
        <p className="max-w-md text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          Upload any song, sing along with the instrumental, and see how closely you matched the
          original — broken down by pitch, tone, and lyrics.
        </p>
      </div>

      <ol className="grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-3">
        {STEPS.map((step, i) => (
          <li
            key={step.title}
            className="flex flex-col gap-1 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
          >
            <span className="text-xs font-medium text-zinc-400 dark:text-zinc-500">
              Step {i + 1}
            </span>
            <span className="text-sm font-semibold text-black dark:text-zinc-50">
              {step.title}
            </span>
            <span className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
              {step.body}
            </span>
          </li>
        ))}
      </ol>

      <div className="flex flex-col items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept="audio/*"
          onChange={handleFileChange}
          disabled={uploading}
          className="text-sm text-zinc-600 file:mr-4 file:rounded-full file:border-0 file:bg-black file:px-4 file:py-2 file:text-sm file:font-medium file:text-white disabled:file:opacity-50 dark:text-zinc-400 dark:file:bg-white dark:file:text-black"
        />

        {uploading && <p className="text-sm text-zinc-500">Uploading…</p>}
        {error && <p className="max-w-sm text-center text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
