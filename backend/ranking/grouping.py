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
from dataclasses import dataclass, field
from pathlib import Path

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


# Chosen on the 484 train packs of the frozen pack split as the smallest
# score at which same-pack precision reaches 0.50
# (research/protocol-grouping-threshold-v1.md; value in
# artifacts/grouping-threshold/grouping_threshold.json). It comes from pack
# co-membership, not from anyone's own grouping choices.
GROUPING_THRESHOLD = 15.3138

# Fragments scored against the new one: the most recent ones with an audio
# vector. A personal library rarely reaches this; the cap bounds the read.
MAX_CANDIDATES = 500


def resolve_artifact(path: str | Path) -> Path:
    """Locate an artifact the way ranking/service.py does.

    Tried as given (relative to the working directory, which is backend/ in
    the container), then relative to the repository root.
    """
    candidate = Path(path)
    if not candidate.is_file() and not candidate.is_absolute():
        candidate = Path(__file__).resolve().parents[2] / candidate
    return candidate


@dataclass(frozen=True)
class Scorable:
    """What the pair score needs from a fragment."""

    fragment_id: str
    vector: Sequence[float]
    bpm: float | None = None
    key: str | None = None
    tags: Sequence[str] = ()
    project_id: str | None = None


@dataclass
class GroupingDecision:
    """join_project, new_project or no_group, and the numbers behind it."""

    action: str
    score: float | None
    threshold: float
    project_id: str | None = None
    fragment_ids: list[str] = field(default_factory=list)
    n_scored: int = 0
    n_unscorable: int = 0

    def record(self) -> dict:
        return {
            "action": self.action,
            "score": None if self.score is None else round(self.score, 4),
            "threshold": self.threshold,
            "project_id": self.project_id,
            "fragment_ids": list(self.fragment_ids),
            "n_scored": self.n_scored,
            "n_unscorable": self.n_unscorable,
        }


def _score(weights, source: Scorable, other: Scorable) -> float:
    return pair_fusion_score(
        weights, source.vector, other.vector, source.bpm, other.bpm,
        source.key, other.key, source.tags, other.tags,
    )


def decide_grouping(
    source: Scorable,
    others: Sequence[Scorable],
    weights: Sequence[float],
    threshold: float = GROUPING_THRESHOLD,
) -> GroupingDecision:
    """Deterministic grouping from the fusion score.

    A project's score is the mean pair score between the new fragment and
    the project's members that have audio vectors (average linkage: one
    close member is not enough to pull a fragment into a project whose
    other members sound different). An ungrouped fragment's score is its
    pair score. The highest-scoring project or fragment wins if it reaches
    the threshold: a project means join_project; an ungrouped fragment
    means new_project with every ungrouped fragment at or above the
    threshold. Otherwise no_group. Ties go to the existing project.
    """
    by_project: dict[str, list[float]] = {}
    loose: list[tuple[float, str]] = []
    unscorable = 0
    for other in others:
        if other.fragment_id == source.fragment_id:
            continue
        try:
            s = _score(weights, source, other)
        except ValueError:
            unscorable += 1
            continue
        if other.project_id:
            by_project.setdefault(other.project_id, []).append(s)
        else:
            loose.append((s, other.fragment_id))
    n_scored = sum(len(v) for v in by_project.values()) + len(loose)

    best_project = max(
        ((float(np.mean(v)), pid) for pid, v in by_project.items()),
        key=lambda t: (t[0], t[1]),
        default=None,
    )
    best_loose = max(loose, key=lambda t: (t[0], t[1]), default=None)
    common = dict(threshold=threshold, n_scored=n_scored, n_unscorable=unscorable)

    if best_project and best_project[0] >= threshold and (
        best_loose is None or best_project[0] >= best_loose[0]
    ):
        return GroupingDecision(
            "join_project", best_project[0], project_id=best_project[1],
            fragment_ids=[source.fragment_id], **common,
        )
    if best_loose and best_loose[0] >= threshold:
        members = [fid for s, fid in sorted(loose, key=lambda t: (-t[0], t[1])) if s >= threshold]
        return GroupingDecision(
            "new_project", best_loose[0], fragment_ids=[source.fragment_id, *members], **common,
        )
    top = max(
        [t[0] for t in (best_project, best_loose) if t is not None], default=None
    )
    return GroupingDecision("no_group", top, **common)
