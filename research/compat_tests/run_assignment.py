"""Assignment on the behavioural-test store: which project does a stem belong to?

Protocol: research/protocol-assignment-v1.md. The mirror image of
run_retrieval: each pair's removed stem is a query, and it is ranked against
candidate contexts (its own and contexts of other tracks), with the stem's
beat-synchronous features pooled on each candidate context's grid. Pools,
scorers, combinations and statistics are retrieval's own functions, used
unchanged. No audio is touched.

  python -m research.compat_tests.run_assignment \
    --store /Volumes/Shirlene/Pocket_Producer/cache/musdb18_v1 \
    --output artifacts/compat-assignment-musdb18
"""

import argparse
import json
import pathlib
import sys

import numpy as np

from . import signals
from .run_behavioral import load_store
from .run_retrieval import (
    COMBINATIONS,
    POOLS,
    RECALL_AT,
    SEED,
    _metric,
    draw_pool,
    on_query_grid,
    rank_of_first,
    standardise,
    summarise,
)

DEFAULT_STORE = pathlib.Path("/Volumes/Shirlene/Pocket_Producer/cache/musdb18_v1")
PRIMARY_POOL = "same_role"
BASELINES = ("fusion5_online", "clap_cos_mean")
CHALLENGERS = ("classic_grid", "classic_onset", "fusion_plus_classic_onset", "cocola")
NEIGHBOUR_FIT = ("chroma_beat_aligned", "onset_pattern")


def check_store(store: pathlib.Path) -> None:
    """Stop with a plain message when the store is missing or empty."""
    if not store.is_dir():
        sys.exit(
            f"Store not found at {store}. The MUSDB18-HQ feature cache lives on an "
            "external drive; connect it (or pass --store) and run again."
        )
    if not any(p for p in store.glob("*.pkl") if not p.name.startswith("._")):
        sys.exit(f"No stored pairs (*.pkl) in {store}; nothing to score.")


def score_contexts(cache: dict, query: str, contexts: list[str], weights, embedders) -> dict:
    """Every scorer for the query stem against each candidate context, true one first.

    The stem is heard placed into each project: its beat-synchronous part is
    pooled on that context's grid, and every scorer sees the context as the
    session and the stem as the candidate.
    """
    rows = [
        signals.score_all(
            cache[context]["context_mix"],
            cache[context]["regions"],
            on_query_grid(cache, context, query),
            weights,
            embedders,
        )
        for context in contexts
    ]
    names = set(rows[0]).intersection(*rows[1:]) if len(rows) > 1 else set(rows[0])
    table = {name: np.array([row[name] for row in rows]) for name in sorted(names)}
    for name, parts in COMBINATIONS.items():
        if all(part in table for part in parts):
            table[name] = np.sum([standardise(table[part]) for part in parts], axis=0)
    return table


def _embedders(cache: dict, pair_ids: list[str]) -> tuple[signals.Embedders | None, str]:
    """COCOLA only when its stored embeddings are present and its checkpoint loads."""
    stored = any("cocola" in cache[pid]["original"].embeddings for pid in pair_ids)
    if not stored:
        return None, "no stored COCOLA embeddings in this store"
    embedders = signals.Embedders(("cocola",))
    try:
        # The scorer loads its checkpoint lazily; load it now so a missing
        # checkpoint skips the comparison here instead of failing mid-run.
        embedders._get("cocola")._load()
    except Exception as exc:  # checkpoint or optional packages missing
        return None, f"COCOLA checkpoint did not load: {type(exc).__name__}: {exc}"
    return embedders, "scored"


def _paired(per_query: dict, first: str, second: str, rng) -> dict | None:
    if first not in per_query or second not in per_query:
        return None
    hit: dict[str, list[float]] = {}
    reciprocal: dict[str, list[float]] = {}
    for pid, (track, rank_first) in per_query[first].items():
        rank_second = per_query[second][pid][1]
        hit.setdefault(track, []).append(float(rank_first <= 1) - float(rank_second <= 1))
        reciprocal.setdefault(track, []).append(1.0 / rank_first - 1.0 / rank_second)
    return {"recall@1": _metric(hit, rng), "mrr": _metric(reciprocal, rng)}


def relation(cache: dict, query: str, neighbour: str) -> str:
    same_song = cache[neighbour]["track"] == cache[query]["track"]
    same_type = cache[neighbour]["role"] == cache[query]["role"]
    if same_song:
        return "other_type_same_song"
    return "same_type_other_song" if same_type else "other_type_other_song"


def _share(labels: list[str]) -> dict:
    kinds = ("same_type_other_song", "other_type_same_song", "other_type_other_song", "none")
    n = len(labels)
    return {
        "n": n,
        **{k: round(labels.count(k) / n, 4) if n else None for k in kinds},
        "counts": {k: labels.count(k) for k in kinds},
    }


def nearest_neighbours(cache: dict, pair_ids: list[str]) -> dict:
    """Each stem's nearest other stem by MS-CLAP cosine and by stem-to-stem fit."""
    product = signals.PRODUCT_MODEL
    have = [pid for pid in pair_ids if product in cache[pid]["original"].embeddings]
    clap_labels: list[str] = []
    if len(have) > 1:
        vectors = np.stack([cache[pid]["original"].embeddings[product] for pid in have])
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        similarity = vectors @ vectors.T
        np.fill_diagonal(similarity, -np.inf)
        for i, pid in enumerate(have):
            clap_labels.append(relation(cache, pid, have[int(np.argmax(similarity[i]))]))

    fit_labels: list[str] = []
    for pid in pair_ids:
        anchor = cache[pid]["original"]
        if cache[pid]["grid"] is None or anchor.beat_chroma is None:
            fit_labels.append("none")
            continue
        others = [q for q in pair_ids if q != pid]
        parts = {name: [] for name in NEIGHBOUR_FIT}
        for other in others:
            scores = signals.beat_scores(anchor, on_query_grid(cache, pid, other))
            for name in NEIGHBOUR_FIT:
                parts[name].append(scores[name])
        total = np.sum([standardise(np.asarray(parts[n])) for n in NEIGHBOUR_FIT], axis=0)
        if not np.any(total != total[0]):
            fit_labels.append("none")
            continue
        fit_labels.append(relation(cache, pid, others[int(np.argmax(total))]))

    return {
        "msclap_cosine": _share(clap_labels),
        "classic_onset_stem_to_stem": _share(fit_labels),
    }


def analyse(cache: dict) -> dict:
    weights = signals.load_fusion_weights()
    rng = np.random.default_rng(SEED)
    pair_ids = sorted(cache)
    embedders, cocola_status = _embedders(cache, pair_ids)

    report = {
        "protocol": "research/protocol-assignment-v1.md",
        "n_queries": len(pair_ids),
        "n_tracks": len({cache[p]["track"] for p in pair_ids}),
        "pool_size": dict(POOLS),
        "primary_pool": PRIMARY_POOL,
        "cocola": cocola_status,
        "chance": {
            pool: {
                **{f"recall@{k}": round(min(1.0, k / size), 4) for k in RECALL_AT},
                "mrr": round(float(np.mean(1.0 / np.arange(1, size + 1))), 4),
                "median_normalised_rank": 0.5,
            }
            for pool, size in POOLS.items()
        },
        "pools": {},
        "by_role": {},
        "differences": {},
    }

    for pool in POOLS:
        ranks: dict[str, dict[str, list[tuple[float, int]]]] = {}
        by_role: dict[str, dict[str, dict[str, list[tuple[float, int]]]]] = {}
        per_query: dict[str, dict[str, tuple[str, float]]] = {}
        for index, pid in enumerate(pair_ids):
            contexts = draw_pool(cache, pair_ids, index, pool)
            if len(contexts) < 2:
                continue
            table = score_contexts(cache, pid, contexts, weights, embedders)
            track, role = cache[pid]["track"], cache[pid]["role"]
            for name, scores in table.items():
                rank = rank_of_first(scores)
                ranks.setdefault(name, {}).setdefault(track, []).append((rank, len(contexts)))
                by_role.setdefault(role, {}).setdefault(name, {}).setdefault(track, []).append(
                    (rank, len(contexts))
                )
                per_query.setdefault(name, {})[pid] = (track, rank)

        report["pools"][pool] = {name: summarise(ranks[name], rng) for name in sorted(ranks)}
        report["by_role"][pool] = {
            role: {name: summarise(items, rng) for name, items in sorted(scorers.items())}
            for role, scorers in sorted(by_role.items())
        }
        report["differences"][pool] = {}
        for challenger in CHALLENGERS:
            for baseline in BASELINES:
                paired = _paired(per_query, challenger, baseline, rng)
                if paired is not None:
                    report["differences"][pool][f"{challenger} - {baseline}"] = paired

    report["nearest_neighbours"] = nearest_neighbours(cache, pair_ids)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=pathlib.Path, default=DEFAULT_STORE)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--dataset", default="musdb18hq")
    args = parser.parse_args()

    check_store(args.store)
    result = analyse(load_store(args.store))
    result["dataset"] = args.dataset
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(result, indent=2))
    print(f"-> {args.output / 'report.json'}")


if __name__ == "__main__":
    main()
