"""Backbone bake-off probes (PocketBench P1/P2 diagnostics).

These measure representation quality only — same-source retrieval and
zero-shot agreement with human annotations. They select which backbones stay
in the race; they say nothing about continuation utility (P3/P4).
"""

import numpy as np


def same_source_recall_at_k(items: list[dict], k: int = 10) -> dict:
    """P1: for each item whose source has >=2 items, does a same-source item
    appear in its top-k nearest neighbours (self excluded)?"""
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item["source_id"]] = by_source.get(item["source_id"], 0) + 1
    eligible = [item for item in items if by_source[item["source_id"]] >= 2]
    if not eligible:
        return {"recall_at_k": None, "k": k, "queries": 0}

    matrix = np.asarray([item["embedding"] for item in items], dtype=np.float64)
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    sources = [item["source_id"] for item in items]
    index_of = {id(item): position for position, item in enumerate(items)}

    hits = 0
    for item in eligible:
        query_index = index_of[id(item)]
        scores = matrix @ matrix[query_index]
        scores[query_index] = -np.inf
        top = np.argpartition(-scores, min(k, len(items) - 1))[:k]
        if any(sources[int(neighbor)] == item["source_id"] for neighbor in top):
            hits += 1
    return {
        "recall_at_k": round(hits / len(eligible), 4),
        "k": k,
        "queries": len(eligible),
    }


def zero_shot_label_accuracy(
    item_embeddings: np.ndarray,
    item_labels: list[list[str]],
    vocabulary: list[str],
    prompt_embeddings: np.ndarray,
) -> dict:
    """P2: predict argmax vocabulary label from prompt cosines; a hit means
    the prediction appears in the item's human labels. Items without labels
    are excluded (never counted as misses)."""
    keep = [index for index, labels in enumerate(item_labels) if labels]
    if not keep:
        return {"accuracy": None, "evaluated": 0}
    audio = item_embeddings[keep]
    audio = audio / np.linalg.norm(audio, axis=1, keepdims=True)
    prompts = prompt_embeddings / np.linalg.norm(
        prompt_embeddings, axis=1, keepdims=True
    )
    predictions = np.argmax(audio @ prompts.T, axis=1)
    hits = sum(
        1
        for row, prediction in zip(keep, predictions, strict=True)
        if vocabulary[int(prediction)] in item_labels[row]
    )
    return {
        "accuracy": round(hits / len(keep), 4),
        "evaluated": len(keep),
        "vocabulary_size": len(vocabulary),
    }
