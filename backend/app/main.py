import json
import logging

import soundfile as sf
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audio_io import convert_to_wav
from app.database import Base, engine, get_db
from app.jobs import process_song, score_attempt_job
from app.models import Attempt, Song
from app.schemas import (
    AssetsResponse,
    AttemptResponse,
    AttemptResultResponse,
    StatusResponse,
    UploadResponse,
)
from app.storage import attempt_dir, attempt_result_path, song_dir
from app.validation import (
    ATTEMPT_ALLOWED_EXTENSIONS,
    SONG_ALLOWED_EXTENSIONS,
    save_upload_with_limit,
    validate_extension,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Singing Similarity Scorer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/songs/upload", response_model=UploadResponse)
def upload_song(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = validate_extension(file.filename, SONG_ALLOWED_EXTENSIONS)

    song = Song(filename=file.filename, status="pending")
    db.add(song)
    db.commit()
    db.refresh(song)

    dest_dir = song_dir(song.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    raw_path = dest_dir / f"upload{ext}"
    wav_path = dest_dir / "original.wav"

    try:
        save_upload_with_limit(file, raw_path)
        # Demucs/librosa can't read compressed containers directly (no system ffmpeg),
        # so normalize every song to a plain WAV up front and store only that.
        convert_to_wav(raw_path, wav_path)
    except HTTPException:
        db.delete(song)
        db.commit()
        raise
    except Exception:
        logger.exception("Failed to decode uploaded song for song_id=%s", song.id)
        wav_path.unlink(missing_ok=True)
        db.delete(song)
        db.commit()
        raise HTTPException(
            status_code=400, detail="Couldn't read that file as audio. Please try a different file."
        )
    finally:
        raw_path.unlink(missing_ok=True)

    background_tasks.add_task(process_song, song.id)

    return UploadResponse(song_id=song.id, status=song.status)


@app.get("/songs/{song_id}/status", response_model=StatusResponse)
def get_song_status(song_id: str, db: Session = Depends(get_db)):
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=404, detail="Song not found")

    return StatusResponse(
        song_id=song.id,
        status=song.status,
        error_message=song.error_message,
        created_at=song.created_at,
    )


@app.get("/songs/{song_id}/assets", response_model=AssetsResponse)
def get_song_assets(song_id: str, db: Session = Depends(get_db)):
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=404, detail="Song not found")

    s_dir = song_dir(song_id)
    instrumental_path = s_dir / "instrumental.wav"
    has_instrumental = instrumental_path.exists()

    duration_sec = None
    if has_instrumental:
        info = sf.info(str(instrumental_path))
        duration_sec = round(info.frames / info.samplerate, 3)

    return AssetsResponse(
        song_id=song.id,
        status=song.status,
        instrumental_url=f"/songs/{song_id}/instrumental" if has_instrumental else None,
        duration_sec=duration_sec,
        has_instrumental=has_instrumental,
        has_reference_vocals=(s_dir / "reference_vocals.wav").exists(),
        has_reference_pitch=(s_dir / "reference_pitch.json").exists(),
        has_reference_lyrics=(s_dir / "reference_lyrics.json").exists(),
    )


@app.get("/songs/{song_id}/instrumental")
def get_instrumental(song_id: str, db: Session = Depends(get_db)):
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=404, detail="Song not found")

    instrumental_path = song_dir(song_id) / "instrumental.wav"
    if not instrumental_path.exists():
        raise HTTPException(status_code=404, detail="Instrumental not ready yet")

    return FileResponse(instrumental_path, media_type="audio/wav", filename="instrumental.wav")


@app.post("/songs/{song_id}/attempts", response_model=AttemptResponse)
def upload_attempt(
    song_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    song = db.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=404, detail="Song not found")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = validate_extension(file.filename, ATTEMPT_ALLOWED_EXTENSIONS)

    attempt = Attempt(song_id=song_id, filename=file.filename, status="scoring")
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    dest_dir = attempt_dir(song_id, attempt.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"original{ext}"

    try:
        save_upload_with_limit(file, dest_path)
    except HTTPException:
        db.delete(attempt)
        db.commit()
        raise

    background_tasks.add_task(score_attempt_job, song_id, attempt.id)

    return AttemptResponse(attempt_id=attempt.id, status=attempt.status)


@app.get("/songs/{song_id}/attempts/{attempt_id}", response_model=AttemptResultResponse)
def get_attempt_result(song_id: str, attempt_id: str, db: Session = Depends(get_db)):
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.song_id != song_id:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status != "scored":
        return AttemptResultResponse(
            attempt_id=attempt.id, status=attempt.status, error_message=attempt.error_message
        )

    try:
        result = json.loads(attempt_result_path(song_id, attempt_id).read_text())
    except (OSError, json.JSONDecodeError):
        logger.exception("result.json missing or unreadable for attempt_id=%s", attempt_id)
        return AttemptResultResponse(
            attempt_id=attempt.id,
            status="failed",
            error_message="Result data is missing. Please try scoring this attempt again.",
        )

    return AttemptResultResponse(attempt_id=attempt.id, status=attempt.status, **result)
