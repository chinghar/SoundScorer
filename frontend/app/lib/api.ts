export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type SongStatus =
  | "pending"
  | "separating"
  | "analyzing_pitch"
  | "transcribing"
  | "ready"
  | "failed";

export interface UploadResponse {
  song_id: string;
  status: string;
}

export interface StatusResponse {
  song_id: string;
  status: SongStatus;
  error_message: string | null;
  created_at: string;
}

export interface AssetsResponse {
  song_id: string;
  status: string;
  instrumental_url: string | null;
  duration_sec: number | null;
  has_instrumental: boolean;
  has_reference_vocals: boolean;
  has_reference_pitch: boolean;
  has_reference_lyrics: boolean;
}

export interface AttemptResponse {
  attempt_id: string;
  status: string;
}

export type AttemptStatus = "scoring" | "scored" | "failed";

export interface SegmentScore {
  start_sec: number;
  end_sec: number;
  overall: number;
  pitch: number;
  tone: number;
  lyrics: number;
}

export interface AttemptResultResponse {
  attempt_id: string;
  status: AttemptStatus;
  error_message: string | null;
  overall_score: number | null;
  pitch_score: number | null;
  tone_score: number | null;
  lyrics_score: number | null;
  segments: SegmentScore[] | null;
}

// Mirrors backend/app/validation.py so obviously-bad files are rejected before
// spending a network round-trip; the backend re-validates independently regardless.
export const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB
export const ALLOWED_AUDIO_EXTENSIONS = [
  ".wav",
  ".mp3",
  ".m4a",
  ".ogg",
  ".oga",
  ".flac",
  ".webm",
  ".aac",
];

export function validateAudioFile(file: File): string | null {
  const dotIndex = file.name.lastIndexOf(".");
  const ext = dotIndex >= 0 ? file.name.slice(dotIndex).toLowerCase() : "";

  if (!ALLOWED_AUDIO_EXTENSIONS.includes(ext)) {
    return `Unsupported file type "${ext || "(none)"}". Please upload an audio file (${ALLOWED_AUDIO_EXTENSIONS.join(", ")}).`;
  }
  if (file.size === 0) {
    return "That file is empty.";
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return `File is too large. Maximum size is ${Math.floor(MAX_UPLOAD_SIZE_BYTES / (1024 * 1024))} MB.`;
  }
  return null;
}

async function extractErrorDetail(res: Response): Promise<string | null> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // response body wasn't JSON; fall back to a generic message
  }
  return null;
}

async function throwForResponse(res: Response, fallback: string): Promise<never> {
  const detail = await extractErrorDetail(res);
  throw new Error(detail ?? `${fallback} (${res.status})`);
}

export async function uploadSong(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/songs/upload`, { method: "POST", body: formData });
  if (!res.ok) return throwForResponse(res, "Upload failed");
  return res.json();
}

export async function getSongStatus(songId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/songs/${songId}/status`);
  if (!res.ok) return throwForResponse(res, "Couldn't fetch song status");
  return res.json();
}

export async function getSongAssets(songId: string): Promise<AssetsResponse> {
  const res = await fetch(`${API_BASE}/songs/${songId}/assets`);
  if (!res.ok) return throwForResponse(res, "Couldn't fetch song assets");
  return res.json();
}

export async function uploadAttempt(songId: string, blob: Blob): Promise<AttemptResponse> {
  const formData = new FormData();
  formData.append("file", blob, "attempt.webm");
  const res = await fetch(`${API_BASE}/songs/${songId}/attempts`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) return throwForResponse(res, "Couldn't submit your recording");
  return res.json();
}

export async function getAttemptResult(
  songId: string,
  attemptId: string
): Promise<AttemptResultResponse> {
  const res = await fetch(`${API_BASE}/songs/${songId}/attempts/${attemptId}`);
  if (!res.ok) return throwForResponse(res, "Couldn't fetch scoring result");
  return res.json();
}

export function instrumentalUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}
