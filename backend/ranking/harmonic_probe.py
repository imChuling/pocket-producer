"""Chroma-based harmonic compatibility probe.

Computes 12-dimensional chroma profiles from audio waveforms and scores
harmonic fit via transpose-invariant cross-correlation. Two chroma
vectors match well when their pitch-class distributions align after an
optimal transposition — capturing key compatibility without requiring
explicit key detection.
"""

import numpy as np

CHROMA_BINS = 12
SEMITONE_NAMES = [
    "C", "C♯", "D", "D♯", "E", "F",
    "F♯", "G", "G♯", "A", "A♯", "B",
]


def chroma_from_audio(
    waveform: np.ndarray,
    sample_rate: int = 22050,
) -> list[float]:
    """Extract a 12-dim mean chroma profile from a waveform.

    Uses CQT-based chroma for better frequency resolution at low
    pitches (bass loops, kick patterns with tonal content).
    """
    import librosa

    mono = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if mono.size == 0:
        return [0.0] * CHROMA_BINS

    chroma = librosa.feature.chroma_cqt(y=mono, sr=sample_rate)
    mean_chroma = chroma.mean(axis=1)

    norm = np.linalg.norm(mean_chroma)
    if norm < 1e-10:
        return [0.0] * CHROMA_BINS
    return (mean_chroma / norm).tolist()


def transpose_invariant_score(
    session_chroma: list[float],
    candidate_chroma: list[float],
) -> tuple[float, int]:
    """Score harmonic fit across all 12 transpositions.

    Returns (best_score, best_shift) where best_shift is the number of
    semitones to transpose the candidate UP to best match the session.
    Score is in [0, 1] (cosine mapped from [-1, 1]).
    """
    s = np.asarray(session_chroma, dtype=np.float64)
    c = np.asarray(candidate_chroma, dtype=np.float64)

    s_norm = np.linalg.norm(s)
    c_norm = np.linalg.norm(c)
    if s_norm < 1e-10 or c_norm < 1e-10:
        return 0.0, 0

    s = s / s_norm
    c = c / c_norm

    best_score = -2.0
    best_shift = 0
    for shift in range(CHROMA_BINS):
        rolled = np.roll(c, shift)
        cosine = float(s @ rolled)
        if cosine > best_score:
            best_score = cosine
            best_shift = shift

    score = round((best_score + 1.0) / 2.0, 6)
    return score, best_shift


def session_chroma(region_chromas: list[list[float]]) -> list[float]:
    """Aggregate per-region chroma vectors into a single session profile."""
    if not region_chromas:
        return [0.0] * CHROMA_BINS
    stacked = np.asarray(region_chromas, dtype=np.float64)
    mean = stacked.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm < 1e-10:
        return [0.0] * CHROMA_BINS
    return (mean / norm).tolist()


def shift_label(semitones: int) -> str:
    """Human-readable label for the optimal transposition."""
    if semitones == 0:
        return "in original key"
    return f"transpose +{semitones} ({SEMITONE_NAMES[semitones % CHROMA_BINS]})"
