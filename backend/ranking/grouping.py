"""Fusion score between two fragments, for deciding project membership.

The deployed fusion-5sig-v1 weights were trained to rank a loop from the
same pack above loops from other packs. Grouping asks the same question of
two fragments, so it reuses those weights on the pair:

  score = w . [cos, cos, tempo, key, tag_jaccard]

With one fragment on each side the mean and max cosine terms are the same
cosine. tempo_match is asymmetric, so it is averaged over both directions;
the key is compared in exact mode after serving_key; tags are compared as
lower-cased sets. research/run_grouping_threshold.py calibrates a threshold
for this score on the frozen pack split and checks its own vectorised
scores against this function.
"""

from collections.abc import Sequence

import numpy as np

from ranking.features import key_match, serving_key, tag_overlap, tempo_match


def pair_signals(
    vec_a: Sequence[float],
    vec_b: Sequence[float],
    bpm_a: float | None,
    bpm_b: float | None,
    key_a: str | None,
    key_b: str | None,
    tags_a: Sequence[str],
    tags_b: Sequence[str],
) -> list[float]:
    """The five fusion signals for one pair; raises if a vector is unusable."""
    a = np.asarray(vec_a, dtype=np.float64)
    b = np.asarray(vec_b, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("audio vectors must be one-dimensional and the same length")
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    if not np.isfinite(norm) or norm < 1e-12:
        raise ValueError("audio vectors must be finite and non-zero")
    cos = float(a @ b) / norm
    tempo = (tempo_match(bpm_a, bpm_b) + tempo_match(bpm_b, bpm_a)) / 2.0
    key = key_match(serving_key(key_a), serving_key(key_b), mode="exact")
    tags = tag_overlap(list(tags_a), list(tags_b))
    return [cos, cos, tempo, key, tags]


def pair_fusion_score(weights: Sequence[float], *args, **kwargs) -> float:
    """Weighted sum of pair_signals under the deployed fusion weights."""
    signals = pair_signals(*args, **kwargs)
    if len(weights) != len(signals):
        raise ValueError(f"expected {len(signals)} weights, got {len(weights)}")
    return float(np.dot(np.asarray(weights, dtype=np.float64), signals))
