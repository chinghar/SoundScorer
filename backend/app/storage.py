from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SONGS_DIR = BACKEND_DIR / "storage" / "songs"


def song_dir(song_id: str) -> Path:
    return SONGS_DIR / song_id


def find_original(song_id: str) -> Path | None:
    matches = sorted(song_dir(song_id).glob("original.*"))
    return matches[0] if matches else None


def attempts_dir(song_id: str) -> Path:
    return song_dir(song_id) / "attempts"


def attempt_dir(song_id: str, attempt_id: str) -> Path:
    return attempts_dir(song_id) / attempt_id


def find_attempt_original(song_id: str, attempt_id: str) -> Path | None:
    matches = sorted(attempt_dir(song_id, attempt_id).glob("original.*"))
    return matches[0] if matches else None


def attempt_result_path(song_id: str, attempt_id: str) -> Path:
    return attempt_dir(song_id, attempt_id) / "result.json"
