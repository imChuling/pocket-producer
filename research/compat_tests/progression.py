"""Progression-aware fit on the session's beat grid.

A mean chroma vector says which pitch classes a clip uses; it cannot say
when. Two loops over the same four chords in a different order have the same
mean chroma and clash on every bar. These scorers compare beat-synchronous
chroma beat by beat, so the order of the harmony counts.

Both inputs are sampled on the context's grid: a candidate dropped into a
session is heard against the session's beats, not its own.
"""

import numpy as np

CHROMA_BINS = 12
MIN_SHARED_BEATS = 4


def _sounding(rows: np.ndarray) -> np.ndarray:
    return np.linalg.norm(rows, axis=1) > 1e-8


def aligned_fit(context: np.ndarray, candidate: np.ndarray) -> float:
    """Mean per-beat chroma agreement as the two clips are, in [0, 1].

    Beats where either side is silent carry no harmonic evidence and are left
    out; with fewer than MIN_SHARED_BEATS left the score is 0.0, the same
    convention the product's features use for missing data.
    """
    beats = min(context.shape[0], candidate.shape[0])
    context, candidate = context[:beats], candidate[:beats]
    both = _sounding(context) & _sounding(candidate)
    if int(both.sum()) < MIN_SHARED_BEATS:
        return 0.0
    left = context[both] / np.linalg.norm(context[both], axis=1, keepdims=True)
    right = candidate[both] / np.linalg.norm(candidate[both], axis=1, keepdims=True)
    return float((left * right).sum(axis=1).mean())


def best_alignment(
    context: np.ndarray, candidate: np.ndarray, max_shift_beats: int = 4
) -> tuple[float, int, int]:
    """Best fit over transpositions and whole-beat delays.

    Returns (score, transposition, delay): the candidate fits best when it is
    transposed UP by `transposition` semitones and started `delay` beats
    later (negative: earlier). Ties go to the smallest change, so an already
    aligned candidate reports (score, 0, 0).
    """
    best = (-1.0, 0, 0)
    order = sorted(range(-max_shift_beats, max_shift_beats + 1), key=abs)
    for delay in order:
        if delay >= 0:
            ctx, cand = context[delay:], candidate[: candidate.shape[0] - delay or None]
        else:
            ctx, cand = context[: context.shape[0] + delay], candidate[-delay:]
        for transposition in range(CHROMA_BINS):
            score = aligned_fit(ctx, np.roll(cand, transposition, axis=1))
            if score > best[0] + 1e-9:
                best = (score, transposition, delay)
    return best


def on_grid_ratio(onsets: np.ndarray, subdivisions: int) -> float:
    """Share of onset energy that falls on sixteenth-note positions.

    `onsets` holds `subdivisions` slots per beat with subdivisions a multiple
    of 4 and at least 8, so every other fine slot lies between sixteenths. A
    part that follows the session grid scores near 1; one that drifts or sits
    off the grid loses energy to the in-between slots.
    """
    if subdivisions < 8 or subdivisions % 4:
        raise ValueError("subdivisions must be a multiple of 4 and at least 8")
    total = float(onsets.sum())
    if total <= 0:
        return 0.0
    step = subdivisions // 4
    slots = np.arange(onsets.shape[0]) % subdivisions
    return float(onsets[slots % step == 0].sum() / total)
