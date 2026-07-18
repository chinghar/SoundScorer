import json
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from app.audio_pipeline import compute_pitch_points_from_signal, transcribe_words
from app.scoring import config as cfg
from app.audio_io import load_audio
from app.scoring.lyrics import score_lyrics
from app.scoring.pitch import score_pitch
from app.scoring.segments import score_segments
from app.scoring.tone import compute_mfcc_frames, score_tone


class AttemptTooQuietError(Exception):
    """Raised when a recording is too short or near-silent to score meaningfully."""


def score_attempt(song_dir: Path, attempt_path: Path) -> dict:
    y_user, sr_user = load_audio(attempt_path)
    duration = len(y_user) / sr_user if sr_user else 0.0
    peak = float(np.max(np.abs(y_user))) if len(y_user) else 0.0

    if duration < cfg.MIN_ATTEMPT_DURATION_SEC or peak < cfg.MIN_ATTEMPT_PEAK_AMPLITUDE:
        raise AttemptTooQuietError(
            f"Recording too short or silent to score (duration={duration:.2f}s, peak={peak:.4f})"
        )

    ref_pitch = json.loads((song_dir / "reference_pitch.json").read_text())
    ref_words = json.loads((song_dir / "reference_lyrics.json").read_text())

    ref_vocals_path = song_dir / "reference_vocals.wav"
    info = sf.info(str(ref_vocals_path))
    song_duration = info.frames / info.samplerate

    # Pitch
    user_pitch = compute_pitch_points_from_signal(y_user, sr_user)
    pitch_score = score_pitch(ref_pitch, user_pitch)

    # Tone
    y_ref, sr_ref = librosa.load(str(ref_vocals_path), sr=None, mono=True)
    ref_mfcc, ref_mfcc_times = compute_mfcc_frames(y_ref, sr_ref)
    user_mfcc, user_mfcc_times = compute_mfcc_frames(y_user, sr_user)
    tone_score = score_tone(ref_mfcc, ref_mfcc_times, user_mfcc, user_mfcc_times)

    # Lyrics
    user_words = transcribe_words(attempt_path)
    lyrics_score = score_lyrics(ref_words, user_words)

    overall_score = (
        cfg.PITCH_WEIGHT * pitch_score + cfg.TONE_WEIGHT * tone_score + cfg.LYRICS_WEIGHT * lyrics_score
    )

    segments = score_segments(
        song_duration,
        ref_pitch, user_pitch,
        ref_mfcc, ref_mfcc_times, user_mfcc, user_mfcc_times,
        ref_words, user_words,
    )

    return {
        "overall_score": round(overall_score, 1),
        "pitch_score": round(pitch_score, 1),
        "tone_score": round(tone_score, 1),
        "lyrics_score": round(lyrics_score, 1),
        "segments": segments,
    }
