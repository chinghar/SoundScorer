from pathlib import Path

from fastapi import HTTPException, UploadFile

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB, generous for a few minutes of audio
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB

# Songs are user-picked files, restricted to what the product intentionally supports.
SONG_ALLOWED_EXTENSIONS = {".mp3", ".mp4"}
# Attempts are always the browser's own MediaRecorder output, never a user file picker.
ATTEMPT_ALLOWED_EXTENSIONS = {".webm"}


def validate_extension(filename: str, allowed: set[str]) -> str:
    """Returns the lowercased extension if it's in `allowed`, else raises a 400."""
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or '(none)'}'. Allowed types: {allowed_str}.",
        )
    return ext


def save_upload_with_limit(file: UploadFile, dest_path: Path) -> None:
    """Streams an upload to disk, rejecting (and cleaning up) if it's empty or oversized."""
    total = 0
    try:
        with dest_path.open("wb") as out_file:
            while chunk := file.file.read(UPLOAD_CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_UPLOAD_SIZE_BYTES:
                    max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
                    raise HTTPException(
                        status_code=400, detail=f"File too large. Maximum size is {max_mb} MB."
                    )
                out_file.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    except HTTPException:
        dest_path.unlink(missing_ok=True)
        raise
