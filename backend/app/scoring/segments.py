import math

import numpy as np

from app.scoring import config as cfg
from app.scoring.lyrics import score_lyrics
from app.scoring.pitch import score_pitch
from app.scoring.tone import score_tone


def build_segments(duration_sec: float) -> list[tuple[float, float]]:
    """Fixed-length windows covering [0, duration_sec) with no gaps or overlaps."""
    if duration_sec <= 0:
        return []
    n_segments = math.ceil(duration_sec / cfg.SEGMENT_LENGTH_SEC)
    return [
        (i * cfg.SEGMENT_LENGTH_SEC, min((i + 1) * cfg.SEGMENT_LENGTH_SEC, duration_sec))
        for i in range(n_segments)
    ]


def score_segments(
    duration_sec: float,
    ref_pitch: list[dict],
    user_pitch: list[dict],
    ref_mfcc: np.ndarray,
    ref_mfcc_times: np.ndarray,
    user_mfcc: np.ndarray,
    user_mfcc_times: np.ndarray,
    ref_words: list[dict],
    user_words: list[dict],
) -> list[dict]:
    """Scores each fixed-length window independently. Coarse segment correspondence
    between reference and user timelines relies on the frontend starting playback and
    recording in the same tick (Phase 3); DTW within each window absorbs local drift."""
    results = []
    for start, end in build_segments(duration_sec):
        window = (start, end)
        pitch = score_pitch(ref_pitch, user_pitch, window)
        tone = score_tone(ref_mfcc, ref_mfcc_times, user_mfcc, user_mfcc_times, window)
        lyrics = score_lyrics(ref_words, user_words, window)
        overall = cfg.PITCH_WEIGHT * pitch + cfg.TONE_WEIGHT * tone + cfg.LYRICS_WEIGHT * lyrics
        results.append({
            "start_sec": round(start, 3),
            "end_sec": round(end, 3),
            "overall": round(overall, 1),
            "pitch": round(pitch, 1),
            "tone": round(tone, 1),
            "lyrics": round(lyrics, 1),
        })
    return results
