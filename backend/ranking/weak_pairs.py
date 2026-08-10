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

import numpy as np

from ranking.features import key_match, tempo_match

CONTEXT_MIN = 2
CONTEXT_MAX = 4


def _context_bpm(context_items: list[dict]) -> float | None:
    values = [item["bpm"] for item in context_items if item.get("bpm")]
    return float(np.mean(values)) if values else None


def _negative_pool(items: list[dict], source_id: str) -> list[dict]:
    return [item for item in items if item["source_id"] != source_id]


def _pick_negatives(
    rng: np.random.Generator,
    pool: list[dict],
    context_items: list[dict],
    positive: dict,
) -> list[tuple[dict, str]]:
    context_bpm = _context_bpm(context_items)
    context_keys = {item.get("key") for item in context_items if item.get("key")}

    def is_easy(item: dict) -> bool:
        tempo_incompatible = (
            context_bpm is not None
            and item.get("bpm")
            and tempo_match(context_bpm, item["bpm"]) == 0.0
        )
        key_incompatible = bool(context_keys) and all(
            key_match(key, item.get("key")) == 0.0 for key in context_keys
        )
        return bool(tempo_incompatible or key_incompatible)

    def is_hard_tempo_key(item: dict) -> bool:
        tempo_ok = (
            context_bpm is not None
            and item.get("bpm")
            and tempo_match(context_bpm, item["bpm"]) > 0.8
        )
        key_ok = not context_keys or any(
            key_match(key, item.get("key")) == 1.0 for key in context_keys
        )
        return bool(tempo_ok and key_ok)

    positive_vector = np.asarray(positive["embedding"])
    chosen: list[tuple[dict, str]] = []
    used_ids: set[str] = set()

    easy_candidates = [item for item in pool if is_easy(item)]
    rng.shuffle(easy_candidates)
    for item in easy_candidates[:2]:
        chosen.append((item, "easy"))
        used_ids.add(item["item_id"])

    hard_tk = [
        item
        for item in pool
        if item["item_id"] not in used_ids and is_hard_tempo_key(item)
    ]
    if hard_tk:
        item = hard_tk[int(rng.integers(len(hard_tk)))]
        chosen.append((item, "hard_tempo_key"))
        used_ids.add(item["item_id"])

    remaining = [item for item in pool if item["item_id"] not in used_ids]
    if remaining:
        similarities = [
            float(np.asarray(item["embedding"]) @ positive_vector)
            for item in remaining
        ]
        item = remaining[int(np.argmax(similarities))]
        chosen.append((item, "hard_similar"))

    return chosen


def build_weak_pairs(items: list[dict], seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    by_source: dict[str, list[dict]] = {}
    for item in items:
        by_source.setdefault(item["source_id"], []).append(item)

    examples: list[dict] = []
    for source_id in sorted(by_source):
        members = sorted(by_source[source_id], key=lambda item: item["item_id"])
        if len(members) < CONTEXT_MIN + 1:
            continue
        pool = _negative_pool(items, source_id)
        if not pool:
            continue
        for positive in members:
            others = [item for item in members if item["item_id"] != positive["item_id"]]
            context_size = int(
                rng.integers(CONTEXT_MIN, min(CONTEXT_MAX, len(others)) + 1)
            )
            picked = rng.choice(len(others), size=context_size, replace=False)
            context_items = [others[index] for index in sorted(picked)]
            negatives = _pick_negatives(rng, pool, context_items, positive)
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
