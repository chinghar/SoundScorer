"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { type AttemptResultResponse, getAttemptResult } from "../../../../lib/api";

type Phase = "loading" | "scoring" | "scored" | "failed" | "network_error";

const POLL_INTERVAL_MS = 1500;
const NETWORK_ERROR_THRESHOLD = 4; // consecutive failures before showing a visible error

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function scoreColorClass(value: number): string {
  if (value >= 80) return "text-emerald-600";
  if (value >= 50) return "text-amber-600";
  return "text-red-600";
}

function Spinner() {
  return (
    <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-600" />
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

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-sm text-zinc-600">
        <span>{label}</span>
        <span className={`font-semibold ${scoreColorClass(value)}`}>{Math.round(value)}</span>
      </div>
      <div className="h-2 w-64 overflow-hidden rounded-full bg-zinc-200">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-600 to-red-600"
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

export default function AttemptResultPage() {
  const params = useParams<{ songId: string; attemptId: string }>();
  const { songId, attemptId } = params;
  const router = useRouter();

  const [phase, setPhase] = useState<Phase>("loading");
  const [result, setResult] = useState<AttemptResultResponse | null>(null);

  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failureCountRef = useRef(0);
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!songId || !attemptId) return;
    cancelledRef.current = false;
    failureCountRef.current = 0;

    poll();
    return () => {
      cancelledRef.current = true;
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [songId, attemptId]);

  async function poll() {
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);

    try {
      const data = await getAttemptResult(songId, attemptId);
      if (cancelledRef.current) return;
      failureCountRef.current = 0;
      setResult(data);

      if (data.status === "scored") {
        setPhase("scored");
        return; // done polling
      } else if (data.status === "failed") {
        setPhase("failed");
        return; // done polling
      } else {
        setPhase("scoring");
      }
    } catch {
      if (cancelledRef.current) return;
      failureCountRef.current += 1;
      if (failureCountRef.current >= NETWORK_ERROR_THRESHOLD) {
        setPhase("network_error");
      }
    }

    if (!cancelledRef.current) {
      pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    }
  }

  function retryPolling() {
    failureCountRef.current = 0;
    setPhase((prev) => (prev === "network_error" ? "scoring" : prev));
    poll();
  }

  function tryAgain() {
    router.push(`/song/${songId}`);
  }

  const chartData =
    result?.segments?.map((s) => ({
      label: formatTime(s.start_sec),
      overall: s.overall,
    })) ?? [];

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 py-16">
      <h1 className="text-2xl font-bold tracking-tight text-white drop-shadow-sm">Results</h1>

      <div className="flex w-full max-w-xl flex-col items-center gap-8 rounded-2xl bg-white/95 p-10 shadow-xl backdrop-blur-sm">
        {(phase === "loading" || phase === "scoring") && (
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-3">
              <Spinner />
              <p className="text-sm text-zinc-600">Scoring…</p>
            </div>
            <p className="text-xs text-zinc-400">
              Comparing your pitch, tone, and lyrics against the original.
            </p>
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

        {phase === "failed" && (
          <div className="flex flex-col items-center gap-4">
            <p className="max-w-sm text-center text-sm text-red-600">
              Scoring failed: {result?.error_message ?? "Unknown error"}
            </p>
            <PrimaryButton onClick={tryAgain}>Try again</PrimaryButton>
          </div>
        )}

        {phase === "scored" && result && (
          <>
            <div className="flex flex-col items-center gap-1">
              <span className="text-xs font-medium uppercase tracking-widest text-zinc-500">
                Overall score
              </span>
              <div className={`text-8xl font-bold ${scoreColorClass(result.overall_score ?? 0)}`}>
                {Math.round(result.overall_score ?? 0)}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <ScoreBar label="Pitch" value={result.pitch_score ?? 0} />
              <ScoreBar label="Tone" value={result.tone_score ?? 0} />
              <ScoreBar label="Lyrics" value={result.lyrics_score ?? 0} />
            </div>

            <div className="flex w-full flex-col gap-2">
              <span className="text-xs font-medium uppercase tracking-widest text-zinc-500">
                Score over time
              </span>
              {chartData.length > 0 ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                      <defs>
                        <linearGradient id="scoreGradient" x1="0" y1="0" x2="1" y2="0">
                          <stop offset="0%" stopColor="#2563eb" />
                          <stop offset="100%" stopColor="#dc2626" />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#88888840" />
                      <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#71717a" }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: "#71717a" }} />
                      <Tooltip />
                      <Area
                        type="monotone"
                        dataKey="overall"
                        stroke="url(#scoreGradient)"
                        strokeWidth={2}
                        fill="url(#scoreGradient)"
                        fillOpacity={0.25}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-sm text-zinc-500">No segment breakdown available.</p>
              )}
            </div>

            <PrimaryButton onClick={tryAgain}>Try again</PrimaryButton>
          </>
        )}
      </div>
    </div>
  );
}
