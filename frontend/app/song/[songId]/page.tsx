"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  type AssetsResponse,
  type SongStatus,
  getSongAssets,
  getSongStatus,
  instrumentalUrl,
  uploadAttempt,
} from "../../lib/api";

type Phase =
  | "loading"
  | "processing"
  | "song_failed"
  | "network_error"
  | "ready"
  | "countdown"
  | "recording"
  | "submitting"
  | "mic_error"
  | "playback_error"
  | "submit_error";

const STAGE_LABELS: Partial<Record<SongStatus, string>> = {
  pending: "Queued…",
  separating: "Separating instrumental and vocals…",
  analyzing_pitch: "Analyzing reference pitch…",
  transcribing: "Transcribing lyrics…",
};

const POLL_INTERVAL_MS = 1500;
const NETWORK_ERROR_THRESHOLD = 4; // consecutive failures before showing a visible error

function Spinner() {
  return (
    <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
  );
}

function BackToUploadLink() {
  return (
    <Link
      href="/"
      className="text-sm font-medium text-zinc-600 underline underline-offset-4 hover:text-black"
    >
      Upload a different song
    </Link>
  );
}

function PrimaryButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded-full bg-gradient-to-r from-blue-600 to-red-600 px-6 py-3 text-sm font-medium text-white transition-transform hover:scale-105"
    >
      {children}
    </button>
  );
}

export default function SongPage() {
  const params = useParams<{ songId: string }>();
  const songId = params.songId;
  const router = useRouter();

  const [phase, setPhase] = useState<Phase>("loading");
  const [songStatus, setSongStatus] = useState<SongStatus | null>(null);
  const [assets, setAssets] = useState<AssetsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState<number | null>(null);

  const audioRef = useRef<HTMLAudioElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failureCountRef = useRef(0);
  const cancelledRef = useRef(false);
  const suppressNextStopRef = useRef(false);

  // Poll status until ready/failed. Doesn't stop polling until assets also load
  // successfully - a transient failure fetching assets right after "ready" used
  // to strand the user on the processing screen forever.
  useEffect(() => {
    if (!songId) return;
    cancelledRef.current = false;
    failureCountRef.current = 0;

    pollSongStatus();
    return () => {
      cancelledRef.current = true;
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [songId]);

  async function pollSongStatus() {
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);

    try {
      const data = await getSongStatus(songId);
      if (cancelledRef.current) return;
      failureCountRef.current = 0;
      setSongStatus(data.status);

      if (data.status === "ready") {
        try {
          const assetsData = await getSongAssets(songId);
          if (cancelledRef.current) return;
          setAssets(assetsData);
          setPhase("ready");
          return; // done polling
        } catch {
          setPhase("processing"); // transient; fall through and retry below
        }
      } else if (data.status === "failed") {
        setError(data.error_message ?? "Processing failed for an unknown reason.");
        setPhase("song_failed");
        return; // done polling
      } else {
        setPhase("processing");
      }
    } catch {
      if (cancelledRef.current) return;
      failureCountRef.current += 1;
      if (failureCountRef.current >= NETWORK_ERROR_THRESHOLD) {
        setPhase("network_error");
      }
    }

    if (!cancelledRef.current) {
      pollTimeoutRef.current = setTimeout(pollSongStatus, POLL_INTERVAL_MS);
    }
  }

  function retryPolling() {
    failureCountRef.current = 0;
    setPhase((prev) => (prev === "network_error" ? "processing" : prev));
    pollSongStatus();
  }

  // Release the mic stream on unmount.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function handleStart() {
    setError(null);

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setPhase("mic_error");
      setError("Microphone access was denied. Please allow microphone access and try again.");
      return;
    }
    streamRef.current = stream;

    try {
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : undefined;
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = handleRecordingStopped;
      mediaRecorderRef.current = recorder;
    } catch {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setPhase("mic_error");
      setError("This browser can't record audio. Please try a different browser.");
      return;
    }

    runCountdown();
  }

  function runCountdown() {
    setPhase("countdown");
    let n = 3;
    setCount(n);
    const interval = setInterval(() => {
      n -= 1;
      if (n <= 0) {
        clearInterval(interval);
        setCount(null);
        beginPlaybackAndRecording();
      } else {
        setCount(n);
      }
    }, 1000);
  }

  function beginPlaybackAndRecording() {
    const audio = audioRef.current;
    const recorder = mediaRecorderRef.current;
    if (!audio || !recorder) return;

    setPhase("recording");
    audio.currentTime = 0;
    audio.play().catch(() => {
      setPhase("playback_error");
      setError("Couldn't start playing the instrumental. Please try again.");
      if (recorder.state !== "inactive") {
        suppressNextStopRef.current = true;
        recorder.stop();
      }
    });

    try {
      recorder.start();
    } catch {
      audio.pause();
      setPhase("playback_error");
      setError("Couldn't start recording. Please try again.");
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    const audio = audioRef.current;
    if (audio && !audio.paused) {
      audio.pause();
    }
  }

  async function handleRecordingStopped() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    if (suppressNextStopRef.current) {
      suppressNextStopRef.current = false;
      return; // recording was aborted due to a playback error; nothing to submit
    }

    const blob = new Blob(chunksRef.current, {
      type: mediaRecorderRef.current?.mimeType || "audio/webm",
    });

    setPhase("submitting");
    try {
      const result = await uploadAttempt(songId, blob);
      router.push(`/song/${songId}/attempt/${result.attempt_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit attempt. Please try again.");
      setPhase("submit_error");
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 py-16">
      <h1 className="text-2xl font-bold tracking-tight text-white drop-shadow-sm">
        Singing Similarity Scorer
      </h1>

      <div className="flex w-full max-w-md flex-col items-center gap-6 rounded-2xl bg-white/95 p-10 shadow-xl backdrop-blur-sm">
        {phase === "loading" && (
          <div className="flex items-center gap-3">
            <Spinner />
            <p className="text-sm text-zinc-500">Loading…</p>
          </div>
        )}

        {phase === "processing" && (
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-3">
              <Spinner />
              <p className="text-sm text-zinc-600">
                {songStatus ? (STAGE_LABELS[songStatus] ?? songStatus) : "Processing…"}
              </p>
            </div>
            <p className="text-xs text-zinc-400">This can take a minute or two on first run.</p>
          </div>
        )}

        {phase === "network_error" && (
          <div className="flex flex-col items-center gap-4">
            <p className="text-center text-sm text-red-600">
              Having trouble reaching the server. Check that the backend is running.
            </p>
            <PrimaryButton onClick={retryPolling}>Retry</PrimaryButton>
          </div>
        )}

        {phase === "song_failed" && (
          <div className="flex flex-col items-center gap-4">
            <p className="max-w-sm text-center text-sm text-red-600">
              Song processing failed: {error}
            </p>
            <BackToUploadLink />
          </div>
        )}

        {phase === "ready" && <PrimaryButton onClick={handleStart}>Start</PrimaryButton>}

        {phase === "countdown" && (
          <div className="flex flex-col items-center gap-2">
            <p className="text-sm font-medium uppercase tracking-widest text-zinc-500">
              Get ready
            </p>
            <div
              key={count}
              className="animate-[countdown-pop_0.5s_ease-out] bg-gradient-to-br from-blue-600 to-red-600 bg-clip-text text-9xl font-bold text-transparent"
            >
              {count}
            </div>
          </div>
        )}

        {phase === "recording" && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" />
              <p className="text-sm text-zinc-600">Recording… sing along!</p>
            </div>
            <button
              onClick={stopRecording}
              className="rounded-full border border-zinc-400 px-5 py-2 text-sm font-medium text-zinc-700 hover:border-zinc-600"
            >
              Stop early
            </button>
          </div>
        )}

        {phase === "submitting" && (
          <div className="flex items-center gap-3">
            <Spinner />
            <p className="text-sm text-zinc-600">Submitting your recording…</p>
          </div>
        )}

        {phase === "mic_error" && (
          <div className="flex flex-col items-center gap-4">
            <p className="max-w-sm text-center text-sm text-red-600">{error}</p>
            <PrimaryButton onClick={handleStart}>Try again</PrimaryButton>
          </div>
        )}

        {phase === "playback_error" && (
          <div className="flex flex-col items-center gap-4">
            <p className="max-w-sm text-center text-sm text-red-600">{error}</p>
            <PrimaryButton onClick={handleStart}>Try again</PrimaryButton>
          </div>
        )}

        {phase === "submit_error" && (
          <div className="flex flex-col items-center gap-4">
            <p className="max-w-sm text-center text-sm text-red-600">{error}</p>
            <div className="flex items-center gap-4">
              <PrimaryButton onClick={() => setPhase("ready")}>Try again</PrimaryButton>
              <BackToUploadLink />
            </div>
          </div>
        )}
      </div>

      {assets?.instrumental_url && (
        <audio
          ref={audioRef}
          src={instrumentalUrl(assets.instrumental_url)}
          onEnded={stopRecording}
          className="hidden"
        />
      )}
    </div>
  );
}
