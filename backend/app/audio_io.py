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


def convert_to_wav(src_path: Path, dest_path: Path) -> None:
    """Decodes any container PyAV understands (mp3, mp4/AAC, etc.) to a WAV file,
    preserving the source's channel count and sample rate.

    Used to normalize song uploads before they reach Demucs/librosa, neither of which
    can read compressed or video containers directly without a system ffmpeg binary.
    """
    import av
    import soundfile as sf

    container = av.open(str(src_path))
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is None:
        raise RuntimeError("No audio stream found in the uploaded file")

    layout = "stereo" if (stream.channels or 1) >= 2 else "mono"
    sr = int(stream.rate)
    resampler = av.audio.resampler.AudioResampler(format="fltp", layout=layout, rate=sr)

    chunks = []
    for frame in container.decode(stream):
        for resampled in resampler.resample(frame):
            chunks.append(resampled.to_ndarray())
    for resampled in resampler.resample(None):
        chunks.append(resampled.to_ndarray())
    container.close()

    if not chunks:
        raise RuntimeError("No audio data could be decoded from the uploaded file")

    data = np.concatenate(chunks, axis=1)  # (channels, samples)
    sf.write(str(dest_path), data.T, sr)  # soundfile wants (samples, channels)
