import numpy as np
import librosa
from dtw import dtw
from scipy.spatial.distance import cdist

from app.audio_pipeline import PITCH_HOP_SEC
from app.scoring.config import MFCC_N


def compute_mfcc_frames(y: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Returns (mfcc frames shaped (n_frames, MFCC_N), frame_times_sec).

    Uses the same hop size as pitch extraction so both modalities' segment
    windows line up on comparable frame boundaries.
    """
    hop_length = max(1, int(sr * PITCH_HOP_SEC))
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=MFCC_N, hop_length=hop_length)
    times = librosa.frames_to_time(np.arange(mfcc.shape[1]), sr=sr, hop_length=hop_length)
    return mfcc.T, times


def score_tone(
    ref_mfcc: np.ndarray,
    ref_times: np.ndarray,
    user_mfcc: np.ndarray,
    user_times: np.ndarray,
    window: tuple[float, float] | None = None,
) -> float:
    ref_frames, user_frames = ref_mfcc, user_mfcc
    if window is not None:
        start, end = window
        ref_frames = ref_mfcc[(ref_times >= start) & (ref_times < end)]
        user_frames = user_mfcc[(user_times >= start) & (user_times < end)]

    if len(ref_frames) == 0:
        return 100.0  # nothing to sing in this range
    if len(user_frames) == 0:
        return 0.0

    cost = cdist(user_frames, ref_frames, metric="cosine")
    cost = np.nan_to_num(cost, nan=1.0)  # near-silent frames have ~0 norm -> undefined cosine

    if cost.shape[0] < 2 or cost.shape[1] < 2:
        n = min(cost.shape[0], cost.shape[1])
        sims = [1.0 - cost[i, i] for i in range(n)]
    else:
        alignment = dtw(cost, keep_internals=False)
        sims = [1.0 - cost[i, j] for i, j in zip(alignment.index1, alignment.index2)]

    avg_sim = float(np.mean(sims)) if sims else 0.0
    return float(np.clip(avg_sim, 0.0, 1.0) * 100.0)
