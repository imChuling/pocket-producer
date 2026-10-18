"""Layer-A weak supervision: leave-one-out pairs from same-source items.

Following Neural Loop Combiner / SampleMatch: items that lived in the same
composition (project, track, pack) are weak positives for each other; typed
negatives come from other sources. These labels are for PRETRAINING only —
they must never be used as human test ground truth, and splits are grouped
by source so the model cannot memorize source identity across the boundary.

Negative types:
  easy            tempo/key clearly incompatible with the context
  hard_tempo_key  compatible tempo AND key, but from another composition
  hard_similar    highest embedding similarity from another composition
"""

import hashlib
from dataclasses import dataclass

import numpy as np

from ranking.features import _TEMPO_TOLERANCE, normalize_key

CONTEXT_MIN = 2
CONTEXT_MAX = 4


def _context_bpm(context_items: list[dict]) -> float | None:
    values = [item["bpm"] for item in context_items if item.get("bpm")]
    return float(np.mean(values)) if values else None


@dataclass(frozen=True)
class _ItemIndex:
    """Per-item arrays, aligned with the input item order."""

    embeddings: np.ndarray
    bpm: np.ndarray
    has_bpm: np.ndarray
    keys: list[str | None]

    @classmethod
    def build(cls, items: list[dict]) -> "_ItemIndex":
        has_bpm = np.array([bool(item.get("bpm")) for item in items])
        bpm = np.array(
            [float(item["bpm"]) if has else 0.0 for item, has in zip(items, has_bpm)]
        )
        return cls(
            embeddings=np.asarray([item["embedding"] for item in items], dtype=np.float64),
            bpm=bpm,
            has_bpm=has_bpm,
            keys=[normalize_key(item.get("key")) for item in items],
        )


def _pick_negatives(
    rng: np.random.Generator,
    items: list[dict],
    index: _ItemIndex,
    pool_rows: np.ndarray,
    context_items: list[dict],
    positive_row: int,
) -> list[tuple[dict, str]]:
    context_bpm = _context_bpm(context_items)
    context_keys = {
        normalize_key(item["key"]) for item in context_items if item.get("key")
    }
    context_keys.discard(None)
    has_context_keys = any(item.get("key") for item in context_items)

    # Same scalar arithmetic as features.tempo_match, applied to the pool at once.
    if context_bpm is not None:
        ratio = np.abs(context_bpm - index.bpm[pool_rows]) / max(context_bpm, 1.0)
        tempo = np.maximum(0.0, 1.0 - ratio / _TEMPO_TOLERANCE)
        has_bpm = index.has_bpm[pool_rows]
        tempo_incompatible = has_bpm & (tempo == 0.0)
        tempo_ok = has_bpm & (tempo > 0.8)
    else:
        tempo_incompatible = np.zeros(len(pool_rows), dtype=bool)
        tempo_ok = tempo_incompatible

    key_in_context = np.array(
        [index.keys[row] is not None and index.keys[row] in context_keys for row in pool_rows],
        dtype=bool,
    )
    key_incompatible = has_context_keys & ~key_in_context
    key_ok = (not has_context_keys) | key_in_context

    easy = tempo_incompatible | key_incompatible
    hard = tempo_ok & key_ok

    chosen: list[tuple[dict, str]] = []
    used_ids: set[str] = set()

    easy_candidates = [items[int(row)] for row in pool_rows[easy]]
    rng.shuffle(easy_candidates)
    for item in easy_candidates[:2]:
        chosen.append((item, "easy"))
        used_ids.add(item["item_id"])

    hard_tk = [
        items[int(row)]
        for row in pool_rows[hard]
        if items[int(row)]["item_id"] not in used_ids
    ]
    if hard_tk:
        item = hard_tk[int(rng.integers(len(hard_tk)))]
        chosen.append((item, "hard_tempo_key"))
        used_ids.add(item["item_id"])

    remaining = [row for row in pool_rows if items[int(row)]["item_id"] not in used_ids]
    if remaining:
        # Row-wise dot products, not one matrix product: the same BLAS path as
        # the original per-item loop, so argmax ties resolve identically.
        positive_vector = index.embeddings[positive_row]
        similarities = [float(index.embeddings[row] @ positive_vector) for row in remaining]
        item = items[int(remaining[int(np.argmax(similarities))])]
        chosen.append((item, "hard_similar"))

    return chosen


def build_weak_pairs(items: list[dict], seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    index = _ItemIndex.build(items)
    row_of = {id(item): row for row, item in enumerate(items)}
    source_rows = np.array([item["source_id"] for item in items])
    by_source: dict[str, list[dict]] = {}
    for item in items:
        by_source.setdefault(item["source_id"], []).append(item)

    examples: list[dict] = []
    for source_id in sorted(by_source):
        members = sorted(by_source[source_id], key=lambda item: item["item_id"])
        if len(members) < CONTEXT_MIN + 1:
            continue
        pool_rows = np.flatnonzero(source_rows != source_id)
        if not len(pool_rows):
            continue
        for positive in members:
            others = [item for item in members if item["item_id"] != positive["item_id"]]
            context_size = int(
                rng.integers(CONTEXT_MIN, min(CONTEXT_MAX, len(others)) + 1)
            )
            picked = rng.choice(len(others), size=context_size, replace=False)
            context_items = [others[index_] for index_ in sorted(picked)]
            negatives = _pick_negatives(
                rng, items, index, pool_rows, context_items, row_of[id(positive)]
            )
            if not negatives:
                continue
            examples.append(
                {
                    "example_id": f"{source_id}:{positive['item_id']}",
                    "source_id": source_id,
                    "context_embeddings": [
                        item["embedding"] for item in context_items
                    ],
                    "context_sources": [
                        item["source_id"] for item in context_items
                    ],
                    "positive_embedding": positive["embedding"],
                    "positive_source": positive["source_id"],
                    "negative_embeddings": [item["embedding"] for item, _ in negatives],
                    "negative_sources": [item["source_id"] for item, _ in negatives],
                    "negative_types": [negative_type for _, negative_type in negatives],
                }
            )
    return examples


def split_sources(
    sources: list[str], seed: int, val_fraction: float = 0.2
) -> tuple[list[str], list[str]]:
    """Deterministic group split: a source is entirely train or entirely val."""
    train: list[str] = []
    val: list[str] = []
    threshold = int(val_fraction * 100)
    for source_id in sorted(set(sources)):
        digest = hashlib.sha256(f"{seed}:{source_id}".encode()).digest()
        (val if digest[0] % 100 < threshold else train).append(source_id)
    return train, val
