"""Central scoring configuration. All scoring weights/thresholds live here only."""

# Overall score = weighted average of pitch/tone/lyrics. Must sum to 1.0.
# Product judgment call: pitch weighted highest (the core "right notes" signal),
# lyrics close behind ("right words"), tone lowest (least reliable signal from
# a phone/laptop mic recording, most sensitive to background noise).
PITCH_WEIGHT = 0.40
TONE_WEIGHT = 0.25
LYRICS_WEIGHT = 0.35

# Per-segment breakdown window. Fixed-length is the MVP-simple choice over
# lyric-line segmentation (nicer UX, more bookkeeping) - see Phase 4 spec.
SEGMENT_LENGTH_SEC = 5.0

# Pitch scoring: cents deviation at/beyond which the pitch score floors at 0.
# 200 cents = 2 semitones, i.e. clearly the wrong note rather than a wobble.
PITCH_CENTS_FOR_ZERO_SCORE = 200.0

# MFCC settings for tone/timbre comparison.
MFCC_N = 13

# Guardrails for degenerate attempts (near-silence / too short to score meaningfully).
MIN_ATTEMPT_DURATION_SEC = 1.0
MIN_ATTEMPT_PEAK_AMPLITUDE = 1e-3

assert abs(PITCH_WEIGHT + TONE_WEIGHT + LYRICS_WEIGHT - 1.0) < 1e-9, "scoring weights must sum to 1.0"
