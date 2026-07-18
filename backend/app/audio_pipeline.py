import json
import shutil
import subprocess
import sys
from pathlib import Path

import librosa

DEMUCS_MODEL = "htdemucs"
PITCH_HOP_SEC = 0.01
PITCH_FMIN_HZ = 65.0
PITCH_FMAX_HZ = 1000.0
WHISPER_MODEL_SIZE = "base"


def separate_stems(original_path: Path, song_dir: Path) -> tuple[Path, Path]:
    """Splits original audio into instrumental + vocal stems via the Demucs CLI.

    CPU-only separation is slow: roughly real-time-or-worse per track length
    (a 30s clip takes ~30-90s on a modern laptop CPU), so this dominates job runtime.
    """
    separate_out = song_dir / "_demucs"
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", DEMUCS_MODEL,
        "--two-stems", "vocals",
        "-o", str(separate_out),
        str(original_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"demucs separation failed: {result.stderr[-2000:]}")

    stem_dir = separate_out / DEMUCS_MODEL / original_path.stem
    vocals_src = stem_dir / "vocals.wav"
    instrumental_src = stem_dir / "no_vocals.wav"
    if not vocals_src.exists() or not instrumental_src.exists():
        raise RuntimeError(f"demucs did not produce expected stems in {stem_dir}")

    instrumental_path = song_dir / "instrumental.wav"
    vocals_path = song_dir / "reference_vocals.wav"
    instrumental_src.replace(instrumental_path)
    vocals_src.replace(vocals_path)

    shutil.rmtree(separate_out, ignore_errors=True)
    return instrumental_path, vocals_path


def compute_pitch_points_from_signal(y, sr: int) -> list[dict]:
    """Runs librosa pyin on an already-decoded mono signal.

    Shared by the Phase 2 reference-pitch pipeline and Phase 4 attempt scoring,
    so both use identical hop size / fmin / fmax and are directly comparable.
    """
    hop_length = max(1, int(sr * PITCH_HOP_SEC))

    f0, _voiced_flag, voiced_prob = librosa.pyin(
        y, fmin=PITCH_FMIN_HZ, fmax=PITCH_FMAX_HZ, sr=sr, hop_length=hop_length,
    )
    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)

    points = []
    for t, freq, conf in zip(times, f0, voiced_prob):
        is_voiced = freq == freq  # NaN check: pyin returns NaN for unvoiced frames
        points.append({
            "time_sec": round(float(t), 3),
            "frequency_hz": round(float(freq), 2) if is_voiced else None,
            "confidence": round(float(conf), 4),
        })
    return points


def compute_pitch_points(audio_path: Path) -> list[dict]:
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    return compute_pitch_points_from_signal(y, sr)


def extract_pitch(vocals_path: Path, output_path: Path) -> None:
    """Runs pitch extraction on the vocal stem and writes a {time_sec, frequency_hz, confidence} series."""
    points = compute_pitch_points(vocals_path)
    output_path.write_text(json.dumps(points))


def transcribe_words(audio_path: Path) -> list[dict]:
    """Runs faster-whisper with word-level timestamps. Shared by reference lyrics and attempt scoring."""
    from faster_whisper import WhisperModel  # heavy import, deferred so app startup stays fast

    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(audio_path), word_timestamps=True)

    words = []
    for segment in segments:
        for word in segment.words or []:
            words.append({
                "word": word.word.strip(),
                "start_sec": round(word.start, 3),
                "end_sec": round(word.end, 3),
            })
    return words


def transcribe_lyrics(vocals_path: Path, output_path: Path) -> None:
    words = transcribe_words(vocals_path)
    output_path.write_text(json.dumps(words))
