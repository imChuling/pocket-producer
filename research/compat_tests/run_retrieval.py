"""Retrieval on the behavioural-test store.

Each pair's context is a query. Its true target is ranked among targets
taken from other tracks, all analysed on the query's own beat grid. No audio
is touched: everything comes from the features the behavioural tests stored.

  python -m research.compat_tests.run_retrieval \
    --store /path/to/store --output artifacts/compat-retrieval-musdb18
"""

import argparse
import dataclasses
import json
import pathlib

import numpy as np

from . import beatgrid, signals
from .run_behavioral import load_store

SEED = 20261113
BOOTSTRAP_RESAMPLES = 2000
RECALL_AT = (1, 5, 10)
# Pool name -> number of candidates including the target.
POOLS = {"any_role": 50, "same_role": 50, "tempo_matched": 10}
# Distractors of the tempo-matched pool come from tracks whose grid tempo is
# within this fraction of the query's, so tempo alone cannot single out the
# target. Queries with too few such tracks are left out of that pool.
TEMPO_TOLERANCE = 0.02

# Sums of scorers standardised within the query's pool. Nothing is fitted.
COMBINATIONS = {
    "classic_grid": ("chroma_beat_aligned", "rhythm_on_grid"),
    "classic_onset": ("chroma_beat_aligned", "onset_pattern"),
    "fusion_plus_classic_grid": ("fusion5_online", "chroma_beat_aligned", "rhythm_on_grid"),
    "fusion_plus_classic_onset": ("fusion5_online", "chroma_beat_aligned", "onset_pattern"),
}
DIFFERENCES = [
    ("classic_grid", "fusion5_online"),
    ("classic_onset", "fusion5_online"),
    ("fusion_plus_classic_grid", "fusion5_online"),
    ("fusion_plus_classic_onset", "fusion5_online"),
    ("cocola", "fusion5_online"),
    ("classic_grid", "cocola"),
    ("classic_onset", "cocola"),
]


def _tempo(entry: dict) -> float | None:
    return entry["grid"].bpm if entry["grid"] is not None else None


def draw_pool(cache: dict, pair_ids: list[str], index: int, pool: str) -> list[str]:
    """The query's own target first, then distractors from other tracks.

    Returns the target alone when the pool cannot be filled, which only
    happens for the tempo-matched pool.
    """
    pid = pair_ids[index]
    entry = cache[pid]
    others = [q for q in pair_ids if cache[q]["track"] != entry["track"]]
    if pool == "same_role":
        others = [q for q in others if cache[q]["role"] == entry["role"]]
    elif pool == "tempo_matched":
        tempo = _tempo(entry)
        if tempo is None:
            return [pid]
        others = [
            q
            for q in others
            if _tempo(cache[q]) is not None
            and abs(_tempo(cache[q]) - tempo) / tempo <= TEMPO_TOLERANCE
        ]
        if len(others) < POOLS[pool] - 1:
            return [pid]
    rng = np.random.default_rng([SEED, index, list(POOLS).index(pool)])
    size = min(POOLS[pool] - 1, len(others))
    return [pid] + [str(q) for q in rng.choice(others, size=size, replace=False)]


def on_query_grid(cache: dict, query: str, candidate: str) -> signals.ClipFeatures:
    """A candidate's features with its beat-synchronous part cut on the query's grid."""
    features = cache[candidate]["original"]
    grid = cache[query]["grid"]
    clip = cache[candidate]["original_frames"]
    if grid is None:
        return dataclasses.replace(features, beat_chroma=None, onsets=None)
    return dataclasses.replace(
        features,
        beat_chroma=beatgrid.pool_chroma(clip, grid),
        onsets=beatgrid.pool_onsets(clip, grid, signals.ONSET_SUBDIVISIONS),
    )


def standardise(values: np.ndarray) -> np.ndarray:
    spread = values.std()
    return (values - values.mean()) / spread if spread > 0 else np.zeros_like(values)


def rank_of_first(scores: np.ndarray) -> float:
    """Rank of item 0, best = 1. Ties share the middle of the ranks they span."""
    better = float((scores[1:] > scores[0]).sum())
    tied = float((scores[1:] == scores[0]).sum())
    return 1.0 + better + tied / 2.0


def score_pool(cache: dict, query: str, candidates: list[str], weights, embedders) -> dict:
    """Every scorer's and combination's scores for the pool, target at index 0."""
    entry = cache[query]
    rows = [
        signals.score_all(
            entry["context_mix"],
            entry["regions"],
            on_query_grid(cache, query, candidate),
            weights,
            embedders,
        )
        for candidate in candidates
    ]
    table = {name: np.array([row[name] for row in rows]) for name in rows[0]}
    for name, parts in COMBINATIONS.items():
        if all(part in table for part in parts):
            table[name] = np.sum([standardise(table[part]) for part in parts], axis=0)
    return table


def _bootstrap(values_by_track: dict[str, list[float]], rng, statistic=np.mean) -> list[float]:
    """Percentile interval for a statistic, resampling whole tracks."""
    tracks = sorted(values_by_track)
    picks = rng.integers(0, len(tracks), size=(BOOTSTRAP_RESAMPLES, len(tracks)))
    if statistic is np.mean:
        sums = np.array([sum(values_by_track[t]) for t in tracks])
        counts = np.array([len(values_by_track[t]) for t in tracks])
        draws = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    else:
        arrays = [np.asarray(values_by_track[t], dtype=np.float64) for t in tracks]
        draws = [float(statistic(np.concatenate([arrays[i] for i in row]))) for row in picks]
    return [round(float(np.percentile(draws, q)), 4) for q in (2.5, 97.5)]


def _metric(values_by_track: dict[str, list[float]], rng, statistic=np.mean) -> dict:
    values = [v for track_values in values_by_track.values() for v in track_values]
    return {
        "value": round(float(statistic(values)), 4),
        "ci95": _bootstrap(values_by_track, rng, statistic),
    }


def summarise(ranks_by_track: dict[str, list[tuple[float, int]]], rng) -> dict:
    """Recall@k, MRR and normalised rank from (rank, pool size) per query."""

    def per_track(function) -> dict[str, list[float]]:
        return {t: [function(r, n) for r, n in items] for t, items in ranks_by_track.items()}

    out = {"n": sum(len(items) for items in ranks_by_track.values())}
    for k in RECALL_AT:
        out[f"recall@{k}"] = _metric(per_track(lambda r, n, k=k: float(r <= k)), rng)
    out["mrr"] = _metric(per_track(lambda r, n: 1.0 / r), rng)
    out["median_normalised_rank"] = _metric(
        per_track(lambda r, n: (r - 1.0) / (n - 1.0)), rng, np.median
    )
    return out


def analyse(cache: dict) -> dict:
    weights = signals.load_fusion_weights()
    rng = np.random.default_rng(SEED)
    pair_ids = sorted(cache)
    uses_cocola = any("cocola" in cache[pid]["original"].embeddings for pid in pair_ids)
    embedders = signals.Embedders(("cocola",)) if uses_cocola else None

    report = {
        "n_queries": len(pair_ids),
        "n_tracks": len({cache[p]["track"] for p in pair_ids}),
        "pool_size": dict(POOLS),
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
            candidates = draw_pool(cache, pair_ids, index, pool)
            if len(candidates) < 2:
                continue
            table = score_pool(cache, pid, candidates, weights, embedders)
            track, role = cache[pid]["track"], cache[pid]["role"]
            for name, scores in table.items():
                rank = rank_of_first(scores)
                ranks.setdefault(name, {}).setdefault(track, []).append((rank, len(candidates)))
                by_role.setdefault(role, {}).setdefault(name, {}).setdefault(track, []).append(
                    (rank, len(candidates))
                )
                per_query.setdefault(name, {})[pid] = (track, rank)

        report["pools"][pool] = {name: summarise(ranks[name], rng) for name in ranks}
        report["by_role"][pool] = {
            role: {name: summarise(items, rng) for name, items in scorers.items()}
            for role, scorers in sorted(by_role.items())
        }
        report["differences"][pool] = {}
        for first, second in DIFFERENCES:
            if first not in per_query or second not in per_query:
                continue
            hit: dict[str, list[float]] = {}
            reciprocal: dict[str, list[float]] = {}
            for pid, (track, rank_first) in per_query[first].items():
                rank_second = per_query[second][pid][1]
                hit.setdefault(track, []).append(float(rank_first <= 1) - float(rank_second <= 1))
                reciprocal.setdefault(track, []).append(1.0 / rank_first - 1.0 / rank_second)
            report["differences"][pool][f"{first} - {second}"] = {
                "recall@1": _metric(hit, rng),
                "mrr": _metric(reciprocal, rng),
            }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--dataset", default="")
    args = parser.parse_args()

    result = analyse(load_store(args.store))
    result["dataset"] = args.dataset
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(result, indent=2))
    print(f"-> {args.output / 'report.json'}")


if __name__ == "__main__":
    main()
