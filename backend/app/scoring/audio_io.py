from pathlib import Path

import numpy as np


def load_audio(path: Path, target_sr: int | None = None) -> tuple[np.ndarray, int]:
    """Decodes arbitrary browser-recorded audio (e.g. webm/opus) to mono float32 PCM.

    Uses PyAV (`av`) directly rather than librosa/soundfile, since libsndfile can't
    read WebM containers and there's no system ffmpeg binary available. `av` is
    already installed as a faster-whisper dependency and bundles its own decoders.
    """
    import av  # deferred: heavy import, only needed when actually scoring

    container = av.open(str(path))
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is None:
        raise RuntimeError("No audio stream found in recording")

    sr = target_sr or int(stream.rate)
    resampler = av.audio.resampler.AudioResampler(format="fltp", layout="mono", rate=sr)

    chunks = []
    for frame in container.decode(stream):
        for resampled in resampler.resample(frame):
            arr = resampled.to_ndarray()
            chunks.append(arr.reshape(-1))
    for resampled in resampler.resample(None):
        arr = resampled.to_ndarray()
        chunks.append(arr.reshape(-1))
    container.close()

    if not chunks:
        return np.zeros(0, dtype=np.float32), sr
    return np.concatenate(chunks).astype(np.float32), sr
