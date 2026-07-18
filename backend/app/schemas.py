from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    song_id: str
    status: str


class StatusResponse(BaseModel):
    song_id: str
    status: str
    error_message: str | None = None
    created_at: datetime


class AttemptResponse(BaseModel):
    attempt_id: str
    status: str


class SegmentScore(BaseModel):
    start_sec: float
    end_sec: float
    overall: float
    pitch: float
    tone: float
    lyrics: float


class AttemptResultResponse(BaseModel):
    attempt_id: str
    status: str
    error_message: str | None = None
    overall_score: float | None = None
    pitch_score: float | None = None
    tone_score: float | None = None
    lyrics_score: float | None = None
    segments: list[SegmentScore] | None = None


class AssetsResponse(BaseModel):
    song_id: str
    status: str
    instrumental_url: str | None = None
    duration_sec: float | None = None
    has_instrumental: bool
    has_reference_vocals: bool
    has_reference_pitch: bool
    has_reference_lyrics: bool
