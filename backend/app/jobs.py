import json
import logging

from app.audio_pipeline import extract_pitch, separate_stems, transcribe_lyrics
from app.database import SessionLocal
from app.models import Attempt, Song
from app.scoring.scorer import AttemptTooQuietError, score_attempt
from app.storage import attempt_result_path, find_attempt_original, find_original, song_dir

logger = logging.getLogger(__name__)

# User-facing fallback messages. Real exception detail is always logged server-side
# via logger.exception so it stays diagnosable without leaking raw tracebacks to clients.
SONG_PROCESSING_FAILURE_MESSAGE = (
    "We couldn't process this song. The file may be corrupted or in an unsupported format."
)
ATTEMPT_SCORING_FAILURE_MESSAGE = "We couldn't score this recording. Please try again."


def _set_status(db, obj, status: str, error_message: str | None = None) -> None:
    obj.status = status
    obj.error_message = error_message
    db.commit()


def process_song(song_id: str) -> None:
    """Runs the Phase 2 pipeline: separation -> pitch extraction -> lyric transcription.

    Stages run strictly in order; a failure at any stage marks the song failed
    and skips the remaining stages.
    """
    db = SessionLocal()
    try:
        song = db.get(Song, song_id)
        if song is None:
            return

        original_path = find_original(song_id)
        if original_path is None:
            _set_status(db, song, "failed", "Original audio file not found")
            return

        s_dir = song_dir(song_id)

        try:
            _set_status(db, song, "separating")
            _instrumental_path, vocals_path = separate_stems(original_path, s_dir)

            _set_status(db, song, "analyzing_pitch")
            extract_pitch(vocals_path, s_dir / "reference_pitch.json")

            _set_status(db, song, "transcribing")
            transcribe_lyrics(vocals_path, s_dir / "reference_lyrics.json")

            _set_status(db, song, "ready")
        except Exception:
            logger.exception("process_song failed for song_id=%s", song_id)
            _set_status(db, song, "failed", SONG_PROCESSING_FAILURE_MESSAGE)
    finally:
        db.close()


def score_attempt_job(song_id: str, attempt_id: str) -> None:
    """Runs Phase 4 scoring for a submitted attempt: scoring -> scored / failed."""
    db = SessionLocal()
    try:
        attempt = db.get(Attempt, attempt_id)
        if attempt is None:
            return

        attempt_path = find_attempt_original(song_id, attempt_id)
        if attempt_path is None:
            _set_status(db, attempt, "failed", "Attempt audio file not found")
            return

        try:
            result = score_attempt(song_dir(song_id), attempt_path)
            attempt_result_path(song_id, attempt_id).write_text(json.dumps(result))
            _set_status(db, attempt, "scored")
        except AttemptTooQuietError as exc:
            # Already a clear, user-readable message - pass it through as-is.
            logger.info("attempt too quiet: song_id=%s attempt_id=%s: %s", song_id, attempt_id, exc)
            _set_status(db, attempt, "failed", str(exc))
        except Exception:
            logger.exception("score_attempt_job failed for song_id=%s attempt_id=%s", song_id, attempt_id)
            _set_status(db, attempt, "failed", ATTEMPT_SCORING_FAILURE_MESSAGE)
    finally:
        db.close()
