import Levenshtein


def _filter_window(words: list[dict], window: tuple[float, float] | None) -> list[dict]:
    if window is None:
        return words
    start, end = window
    return [w for w in words if start <= w["start_sec"] < end]


def _encode(words: list[str], vocab: dict[str, str]) -> str:
    """Maps each distinct word to a private-use character so python-Levenshtein
    (which operates on strings) can compute word-level, not character-level, edit distance."""
    chars = []
    for w in words:
        key = w.strip().lower()
        if key not in vocab:
            # 0xE000 is the start of the actual Unicode Private Use Area (0x400 is
            # Cyrillic); using real PUA code points avoids any chance of colliding
            # with normal text if this is ever logged, printed, or compared elsewhere.
            vocab[key] = chr(0xE000 + len(vocab))
        chars.append(vocab[key])
    return "".join(chars)


def score_lyrics(
    ref_words: list[dict], user_words: list[dict], window: tuple[float, float] | None = None
) -> float:
    """Word Error Rate-based score: 100 * (1 - (substitutions+deletions+insertions)/len(ref))."""
    ref = _filter_window(ref_words, window)
    user = _filter_window(user_words, window)

    if not ref:
        return 100.0  # nothing to sing in this range
    if not user:
        return 0.0

    vocab: dict[str, str] = {}
    ref_enc = _encode([w["word"] for w in ref], vocab)
    user_enc = _encode([w["word"] for w in user], vocab)

    ops = Levenshtein.editops(ref_enc, user_enc)
    substitutions = sum(1 for op, _, _ in ops if op == "replace")
    deletions = sum(1 for op, _, _ in ops if op == "delete")
    insertions = sum(1 for op, _, _ in ops if op == "insert")

    word_error_rate = (substitutions + deletions + insertions) / len(ref)
    score = 100.0 * (1.0 - word_error_rate)
    return max(0.0, min(100.0, score))
