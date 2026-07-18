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
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  async function handleFile(file: File) {
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

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function handleDragEnter(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (uploading) return;
    dragCounterRef.current += 1;
    setIsDragging(true);
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragging(false);
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDragging(false);
    if (uploading) return;

    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-10 px-6 py-16">
      <div className="flex flex-col items-center gap-3 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-white drop-shadow-sm">
          Singing Similarity Scorer
        </h1>
        <p className="max-w-md text-sm leading-relaxed text-white/90">
          Upload any song, sing along with the instrumental, and see how closely you matched the
          original — broken down by pitch, tone, and lyrics.
        </p>
      </div>

      <ol className="grid w-full max-w-2xl grid-cols-1 gap-4 sm:grid-cols-3">
        {STEPS.map((step, i) => (
          <li
            key={step.title}
            className="flex flex-col gap-1 rounded-xl border border-white/20 bg-white/10 p-4 backdrop-blur-sm"
          >
            <span className="text-xs font-medium text-white/70">Step {i + 1}</span>
            <span className="text-sm font-semibold text-white">{step.title}</span>
            <span className="text-xs leading-relaxed text-white/80">{step.body}</span>
          </li>
        ))}
      </ol>

      <div className="w-full max-w-md rounded-2xl bg-white/95 p-8 shadow-xl backdrop-blur-sm">
        <div
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !uploading && inputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
            isDragging
              ? "border-blue-500 bg-blue-50"
              : "border-zinc-300 bg-zinc-50 hover:border-zinc-400"
          } ${uploading ? "pointer-events-none opacity-60" : ""}`}
        >
          <svg
            className="h-8 w-8 text-zinc-400"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
            />
          </svg>
          <p className="text-sm font-medium text-zinc-700">
            {isDragging ? "Drop your song here" : "Drag and drop your song here"}
          </p>
          <p className="text-xs text-zinc-500">or click to browse</p>

          <input
            ref={inputRef}
            type="file"
            accept="audio/mpeg,video/mp4,audio/mp4,.mp3,.mp4"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />
        </div>

        <p className="mt-3 text-center text-xs text-zinc-500">
          MP3 or MP4 only, up to 50MB.
        </p>

        {uploading && (
          <p className="mt-3 text-center text-sm text-zinc-600">Uploading…</p>
        )}
        {error && <p className="mt-3 text-center text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
