import numpy as np
from dtw import dtw

from app.scoring.config import PITCH_CENTS_FOR_ZERO_SCORE


def _filter_window(points: list[dict], window: tuple[float, float] | None) -> list[dict]:
    if window is None:
        return points
    start, end = window
    return [p for p in points if start <= p["time_sec"] < end]


def score_pitch(
    ref_points: list[dict], user_points: list[dict], window: tuple[float, float] | None = None
) -> float:
    """DTW-aligns two pitch contours and scores average cents deviation on frames voiced in both.

    ref_points/user_points: [{time_sec, frequency_hz (nullable), confidence}, ...]
    """
    ref = _filter_window(ref_points, window)
    user = _filter_window(user_points, window)

    ref_voiced_count = sum(1 for p in ref if p["frequency_hz"] is not None)
    if ref_voiced_count == 0:
        return 100.0  # nothing to sing in this range
    if not user:
        return 0.0  # reference has content, user recording has none

    ref_freq = np.array([p["frequency_hz"] or 0.0 for p in ref], dtype=np.float64)
    user_freq = np.array([p["frequency_hz"] or 0.0 for p in user], dtype=np.float64)
    ref_voiced = np.array([p["frequency_hz"] is not None for p in ref])
    user_voiced = np.array([p["frequency_hz"] is not None for p in user])

    if len(ref_freq) < 2 or len(user_freq) < 2:
        n = min(len(ref_freq), len(user_freq))
        index1, index2 = np.arange(n), np.arange(n)
    else:
        alignment = dtw(user_freq, ref_freq, keep_internals=False)
        index1, index2 = alignment.index1, alignment.index2

    cents_devs = []
    for i, j in zip(index1, index2):
        if user_voiced[i] and ref_voiced[j]:
            cents = 1200.0 * np.log2(user_freq[i] / ref_freq[j])
            cents_devs.append(abs(cents))

    if not cents_devs:
        return 0.0  # aligned but never overlapped on a voiced frame

    avg_cents = float(np.mean(cents_devs))
    score = 100.0 * (1.0 - avg_cents / PITCH_CENTS_FOR_ZERO_SCORE)
    return float(np.clip(score, 0.0, 100.0))
