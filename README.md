# Singing Similarity Scorer

Upload a song, sing along to it, and see how closely you matched the original — broken down
by pitch, tone, and lyrics, with a timeline showing which parts you nailed vs. struggled with.

## Structure

- `frontend/` — Next.js + TypeScript + Tailwind + recharts.
  - `/` — upload a song.
  - `/song/[songId]` — processing status, then a 3-2-1 countdown, sing-along recording.
  - `/song/[songId]/attempt/[attemptId]` — scoring status, then results with a timeline chart.
- `backend/` — FastAPI + SQLAlchemy (SQLite). Background jobs (no Celery/Redis) do the heavy lifting:
  source separation, pitch extraction, lyric transcription, and attempt scoring.

## Run locally

Two terminals, no Docker required. Requires Python 3.11+ and Node 18+.

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000` (interactive docs at `/docs`). SQLite DB is created at
`backend/app.db` on first run. Uploaded files and generated artifacts are saved under
`backend/storage/songs/{song_id}/`.

Notes on first run:
- `demucs` (source separation) and `faster-whisper` (transcription) download their models the
  first time they're used — expect the first upload to take noticeably longer than subsequent ones.
- Everything runs on CPU. A ~30s song takes roughly 30-90s to fully process on a modern laptop;
  scoring an attempt takes somewhat less.
- No system `ffmpeg` is required — audio decoding (including the browser's webm/opus recordings)
  goes through `av` (PyAV), which bundles its own decoders.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`. It calls the backend at `http://localhost:8000` by
default (override with `NEXT_PUBLIC_API_BASE_URL` if the backend runs elsewhere).

## Try it

1. Start both servers above.
2. Open `http://localhost:3000`, drag and drop (or click to browse) a song — MP3 or MP4, ≤50MB.
3. Wait for processing (separating → analyzing pitch → transcribing → ready).
4. Click Start, allow microphone access, sing along through the 3-2-1 countdown.
5. Recording stops automatically when the song ends and is submitted for scoring.
6. Watch the results page for your overall score, pitch/tone/lyrics breakdown, and timeline chart.

## How scoring works

When an attempt is submitted, the backend decodes the recording (via PyAV, so browser webm/opus
works directly) and extracts the same pitch contour (librosa `pyin`) and MFCC timbre features used
for the reference vocal, then DTW-aligns (`dtw-python`) the user's contour to the reference to
absorb timing drift before comparing them. **Pitch accuracy** is the average cents deviation on
frames voiced in both recordings, mapped to 0-100. **Tone accuracy** is average cosine similarity
between DTW-aligned MFCC frames. **Lyrics accuracy** is a Word Error Rate score from word-level
Levenshtein distance (`python-Levenshtein`) between the reference transcript and a fresh
`faster-whisper` transcription of the attempt. The overall score is a weighted average
(pitch 40% / tone 25% / lyrics 35%, see `backend/app/scoring/config.py`), computed both for the
whole recording and independently for each fixed 5-second segment to produce the timeline chart.
Recordings that are too short or near-silent are rejected with a clear error rather than scored.

## API

- `POST /songs/upload` — multipart form, field `file`. Returns `{ song_id, status }`.
  Only `.mp3`/`.mp4` are accepted; rejects other extensions, empty files, and files over 50MB
  with a 400 + clear message. Accepted files are normalized to a plain WAV (`original.wav`)
  before processing, since Demucs/librosa can't read compressed containers directly.
- `GET /songs/{song_id}/status` — `{ song_id, status, error_message, created_at }`.
  `status`: `pending` → `separating` → `analyzing_pitch` → `transcribing` → `ready` | `failed`.
- `GET /songs/{song_id}/assets` — instrumental URL, duration, and which reference artifacts exist.
- `GET /songs/{song_id}/instrumental` — streams the separated instrumental audio.
- `POST /songs/{song_id}/attempts` — multipart form, field `file` (the user's recording).
  Same validation as song upload. Returns `{ attempt_id, status }`.
- `GET /songs/{song_id}/attempts/{attempt_id}` — scoring status, and once `status: "scored"`,
  the full result: `{ overall_score, pitch_score, tone_score, lyrics_score, segments: [...] }`.
  `status`: `scoring` → `scored` | `failed`.

## Known limitations

- Single-process, in-memory background jobs (`BackgroundTasks`) — fine for local/demo use, not
  for concurrent multi-user production load. A real deployment would want a proper task queue.
- No auth, accounts, or history — every song/attempt is anonymous and world-readable by ID.
- CORS is locked to `http://localhost:3000`; update `backend/app/main.py` if you serve the
  frontend from elsewhere.
