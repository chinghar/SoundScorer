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
`backend/storage/app.db` on first run. Uploaded files and generated artifacts are saved under
`backend/storage/songs/{song_id}/`. (Everything lives under `storage/` so a single volume mount
covers all persistent state — see Deployment below.)

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

## Deployment

The frontend and backend are packaged as **one Docker image** (`Dockerfile` at the repo root):
Next.js (`output: "standalone"`) and FastAPI run as separate processes in the same container,
with Caddy reverse-proxying `/songs/*` to the backend and everything else to the frontend. This
means one host, one URL, no CORS, and no separate `NEXT_PUBLIC_API_BASE_URL` wiring between two
services — but it's still a real, always-on server under the hood, so it needs to run somewhere
with genuine persistent compute, **not** Vercel or another serverless platform (see below).

### Why not Vercel

Vercel runs Python as serverless functions: they freeze immediately after the HTTP response is
sent, so the `BackgroundTasks` jobs this app depends on (Demucs separation, transcription, scoring)
would get killed mid-run. The filesystem is also ephemeral, so SQLite and uploaded files wouldn't
persist. And `torch` + `demucs` + `faster-whisper` alone are hundreds of MB, past Vercel's function
size limit. None of this is a config problem — the backend needs a persistent server, full stop.

### Resource requirements

Budget **2GB+ RAM**. Loading the Demucs model plus torch's runtime commonly uses 1GB+ during
separation; smaller instances (Render/Fly/Railway's smallest free or hobby tiers, ~256-512MB)
will likely OOM-crash on the first real song upload.

### Deploying to an Oracle Cloud "Always Free" VM

Oracle Cloud's Always Free tier is one of the few genuinely permanent free tiers with enough RAM
for this app (up to 24GB on the ARM Ampere A1 shape).

1. **Create the VM**: [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) → sign up (a
   card is required for identity verification, but Always Free resources aren't charged) →
   Compute → Instances → Create Instance. Pick an **Ampere A1 (ARM)** shape, Always Free eligible
   (e.g. 2 OCPU / 12GB RAM), Ubuntu image, and add your SSH key (`ssh-keygen` if you don't have
   one). Make sure it's assigned a public IP.

2. **Open port 80** — Oracle Cloud blocks it in *two* places by default, both need fixing:
   - Cloud-level: the VM's subnet → Security Lists (or Network Security Groups) → add an
     ingress rule: source `0.0.0.0/0`, TCP, destination port `80`.
   - VM-level firewall: SSH in and run
     `sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT && sudo netfilter-persistent save`
     (Ubuntu images ship with their own iptables rules that block it even after the cloud-level
     rule is open).

3. **Install Docker** on the VM:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER && newgrp docker
   ```

4. **Deploy**:
   ```bash
   git clone https://github.com/chinghar/SoundScorer.git
   cd SoundScorer
   docker compose up -d --build
   ```

5. Visit `http://<VM_PUBLIC_IP>`. First song upload will be slow (models download on first use,
   cached afterward in the `model_cache` volume so restarts don't re-download them).

To redeploy after pulling new code: `git pull && docker compose up -d --build`.

I haven't been able to test-build or run this image myself (no local Docker available in this
environment) — the Dockerfile/Caddyfile/compose setup follows standard, well-established patterns,
but treat the first `docker compose up --build` as the real first test.

## Known limitations

- Single-process, in-memory background jobs (`BackgroundTasks`) — fine for local/demo use, not
  for concurrent multi-user production load. A real deployment would want a proper task queue.
- No auth, accounts, or history — every song/attempt is anonymous and world-readable by ID.
- CORS is locked to `http://localhost:3000`; update `backend/app/main.py` if you serve the
  frontend from elsewhere.
<!-- doc pass 1 -->
<!-- doc pass 2 -->
<!-- doc pass 3 -->
<!-- doc pass 4 -->
<!-- doc pass 5 -->
