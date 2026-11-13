"""Behavioural tests for compatibility scorers.

For every (context, target) pair, score the original target and each
perturbed copy against the context with every scorer, then report how
often the original wins.

Two stages, run from the repository root:

  python -m research.compat_tests.run_behavioral features \
    --dataset babyslakh --root /path/to/babyslakh_16k --store /path/to/store
  python -m research.compat_tests.run_behavioral report \
    --store /path/to/store --output artifacts/compat-behavioral-dev

`features` writes one file per pair and skips pairs already done, so it can
be interrupted, resumed, and run as several processes with --shard i/n.
"""

import argparse
import dataclasses
import json
import pathlib
import pickle
import time

import numpy as np

from . import beatgrid, datasets, musdb, perturb, progression, signals

BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261112
RANDOM_NEGATIVES = 8
CONTROL_FOR = {"pitch": "pitch_roundtrip", "tempo": "tempo_roundtrip"}
# A whole-beat delay only clashes where the harmony moves: below this much
# change between the target and its delayed self there is nothing to detect.
MIN_HARMONIC_CHANGE = 0.05
# Families pooled into one figure per scorer, and what each is compared with.
POOLED = {
    "pitch_vs_control": ("pitch", "directional", "control"),
    "tempo_vs_control": ("tempo", "directional", "control"),
    "varispeed": ("varispeed", "directional", "original"),
}


def _store_path(store: pathlib.Path, pair_id: str) -> pathlib.Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in pair_id)
    return store / f"{safe}.pkl"


def compute_features(pairs, embedders: signals.Embedders, store: pathlib.Path) -> None:
    """Features for the context, the original and every perturbed copy of each pair."""
    store.mkdir(parents=True, exist_ok=True)
    catalogue = perturb.catalogue()
    started = time.time()
    done = 0
    for pair in pairs:
        path = _store_path(store, pair.pair_id)
        entry = pickle.loads(path.read_bytes()) if path.exists() else None
        sr = pair.sample_rate
        context_frames = beatgrid.frames(pair.context_mix, sr)
        grid = beatgrid.grid_from_frames(context_frames) if context_frames is not None else None
        beat_seconds = 60.0 / grid.bpm if grid is not None else None
        wanted = [
            item for item in catalogue if perturb.applicable(item, pair.pitched, beat_seconds)
        ]
        if entry is not None and all(item.name in entry["perturbed"] for item in wanted):
            continue
        if entry is None:
            original, original_frames = signals.clip_features(
                perturb.original(pair.target_padded, sr), sr, embedders, grid
            )
            entry = {
                "pair_id": pair.pair_id,
                "track": pair.track,
                "role": pair.role,
                "pitched": pair.pitched,
                "grid": grid,
                "context_mix": signals.clip_features(pair.context_mix, sr, embedders, grid)[0],
                # Session regions feed only the product's own cosine terms.
                "regions": [
                    signals.clip_features(r, sr, embedders, models=(signals.PRODUCT_MODEL,))[0]
                    for r in pair.regions
                ],
                "original": original,
                "original_frames": original_frames,
                "perturbed": {},
            }
        # A stored pair only computes the perturbations added since it was stored.
        for item in wanted:
            if item.name not in entry["perturbed"]:
                clip = perturb.apply(item, pair.target_padded, sr, beat_seconds)
                entry["perturbed"][item.name] = signals.clip_features(clip, sr, embedders, grid)[0]
        path.write_bytes(pickle.dumps(entry))
        done += 1
        print(f"[{done}] {pair.pair_id} {pair.role} ({time.time() - started:.0f}s)", flush=True)


def load_store(store: pathlib.Path) -> dict:
    # macOS leaves "._name" companion files on non-native volumes; they are not pickles.
    paths = sorted(p for p in store.glob("*.pkl") if not p.name.startswith("._"))
    entries = [pickle.loads(path.read_bytes()) for path in paths]
    return {entry["pair_id"]: entry for entry in entries}


def foreign_candidates(cache: dict) -> dict[str, dict[str, signals.ClipFeatures]]:
    """Each pair's random negatives, cut on that pair's own beat grid.

    A target from another track is heard against this context's beats, so
    its beat-synchronous features are pooled again from its stored frames.
    """
    pair_ids = sorted(cache)
    chosen_for: dict[str, dict[str, signals.ClipFeatures]] = {}
    for index, pid in enumerate(pair_ids):
        entry = cache[pid]
        others = [q for q in pair_ids if cache[q]["track"] != entry["track"]]
        rng = np.random.default_rng([BOOTSTRAP_SEED, index])
        chosen = rng.choice(others, size=min(RANDOM_NEGATIVES, len(others)), replace=False)
        grid = entry["grid"]
        chosen_for[pid] = {}
        for other in chosen:
            features = cache[other]["original"]
            if grid is None:
                candidate = dataclasses.replace(features, beat_chroma=None, onsets=None)
            else:
                clip = cache[other]["original_frames"]
                candidate = dataclasses.replace(
                    features,
                    beat_chroma=beatgrid.pool_chroma(clip, grid),
                    onsets=beatgrid.pool_onsets(clip, grid, signals.ONSET_SUBDIVISIONS),
                )
            chosen_for[pid][str(other)] = candidate
    return chosen_for


def _bootstrap_ci(values_by_track: dict[str, list[float]], rng) -> list[float]:
    """Percentile interval for the mean, resampling whole tracks."""
    tracks = sorted(values_by_track)
    sums = np.array([sum(values_by_track[t]) for t in tracks])
    counts = np.array([len(values_by_track[t]) for t in tracks])
    picks = rng.integers(0, len(tracks), size=(BOOTSTRAP_RESAMPLES, len(tracks)))
    means = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    return [round(float(np.percentile(means, q)), 4) for q in (2.5, 97.5)]


def _win(delta: float) -> float:
    return 1.0 if delta > 0 else 0.5 if delta == 0 else 0.0


def _summary(deltas_by_track: dict[str, list[float]], scale: float, rng) -> dict:
    deltas = [d for values in deltas_by_track.values() for d in values]
    wins = {track: [_win(d) for d in values] for track, values in deltas_by_track.items()}
    return {
        "n": len(deltas),
        "wins": round(float(np.mean([w for values in wins.values() for w in values])), 4),
        "ci95": _bootstrap_ci(wins, rng),
        "tie_rate": round(float(np.mean([d == 0 for d in deltas])), 4),
        # Mean score drop in units of the scorer's spread over random candidates.
        "drop_in_sd": round(float(np.mean(deltas)) / scale, 4) if scale > 0 else None,
    }


def analyse(cache: dict) -> dict:
    """Win rates of the original over each perturbed copy, per scorer.

    Pitch and tempo perturbations are also compared against their round-trip
    control, which went through the same processing but ended at the original
    pitch or tempo. A scorer that only reacts to processing artefacts beats
    the perturbed copy with the original but not with the control.
    """
    weights = signals.load_fusion_weights()
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    pair_ids = sorted(cache)
    catalogue = {item.name: item for item in perturb.catalogue()}
    uses_cocola = any("cocola" in cache[pid]["original"].embeddings for pid in pair_ids)
    embedders = signals.Embedders(("cocola",)) if uses_cocola else None

    def scores_for(pid: str, features) -> dict[str, float]:
        entry = cache[pid]
        return signals.score_all(
            entry["context_mix"], entry["regions"], features, weights, embedders
        )

    original = {pid: scores_for(pid, cache[pid]["original"]) for pid in pair_ids}
    perturbed = {
        pid: {name: scores_for(pid, feats) for name, feats in cache[pid]["perturbed"].items()}
        for pid in pair_ids
    }
    scorers = [name for name in signals.SCORER_NAMES if name in original[pair_ids[0]]]

    # Reference: the true target against targets taken from other tracks.
    random_deltas = {name: {} for name in scorers}
    random_scores = {name: [] for name in scorers}
    for pid, candidates in foreign_candidates(cache).items():
        track = cache[pid]["track"]
        for candidate in candidates.values():
            scores = scores_for(pid, candidate)
            for name in scorers:
                random_deltas[name].setdefault(track, []).append(original[pid][name] - scores[name])
                random_scores[name].append(scores[name])
    scale = {name: float(np.std(random_scores[name])) for name in scorers}

    report = {
        "n_pairs": len(pair_ids),
        "n_tracks": len({cache[p]["track"] for p in pair_ids}),
        "roles": {},
        "scorers": scorers,
        "reference_true_vs_random": {
            name: _summary(random_deltas[name], scale[name], rng) for name in scorers
        },
        "pooled": {},
        "tests": {},
    }
    for pid in pair_ids:
        role = cache[pid]["role"]
        report["roles"][role] = report["roles"].get(role, 0) + 1

    def harmony_moves(pid: str, test_name: str) -> bool:
        """The target's own chords differ between where it was and where the delay puts it."""
        before, after = cache[pid]["original"], cache[pid]["perturbed"][test_name]
        if before.beat_chroma is None or after.beat_chroma is None:
            return False
        fit = progression.aligned_fit(before.beat_chroma, after.beat_chroma)
        return fit > 0 and 1.0 - fit >= MIN_HARMONIC_CHANGE

    def recovered(pid: str, features) -> tuple[int, int] | None:
        context = cache[pid]["context_mix"]
        if context.beat_chroma is None or features.beat_chroma is None:
            return None
        return progression.best_alignment(context.beat_chroma, features.beat_chroma)[1:]

    subsets = {
        "pitched": lambda pid, test: cache[pid]["pitched"],
        "drums": lambda pid, test: not cache[pid]["pitched"],
        "harmony_moves": lambda pid, test: cache[pid]["pitched"] and harmony_moves(pid, test),
    }

    for test_name, item in catalogue.items():
        control = CONTROL_FOR.get(item.family)
        rows = {}
        for name in scorers:
            versus_original: dict[str, list[float]] = {}
            versus_control: dict[str, list[float]] = {}
            by_subset: dict[str, dict[str, list[float]]] = {key: {} for key in subsets}
            for pid in pair_ids:
                if test_name not in perturbed[pid]:
                    continue
                track = cache[pid]["track"]
                score = perturbed[pid][test_name][name]
                delta = original[pid][name] - score
                versus_original.setdefault(track, []).append(delta)
                for key, members in by_subset.items():
                    if key == "harmony_moves" and item.family != "beatshift":
                        continue
                    if subsets[key](pid, test_name):
                        members.setdefault(track, []).append(delta)
                if control and control in perturbed[pid]:
                    versus_control.setdefault(track, []).append(
                        perturbed[pid][control][name] - score
                    )
            if not versus_original:
                continue
            rows[name] = {"vs_original": _summary(versus_original, scale[name], rng)}
            if versus_control:
                rows[name]["vs_control"] = _summary(versus_control, scale[name], rng)
            for key, members in by_subset.items():
                if members:
                    rows[name][key] = _summary(members, scale[name], rng)
        if not rows:
            continue
        report["tests"][test_name] = {
            "kind": item.kind,
            "family": item.family,
            "value": item.value,
            "control": control,
            "scorers": rows,
        }

        # Equivariance: does the alignment search name the change that was made?
        expected = None
        if item.family == "pitch":
            expected = ("transposition", int(-item.value) % 12)
        elif item.family == "beatshift" and float(item.value).is_integer():
            expected = ("delay", -int(item.value))
        if expected is not None:
            hits_by_track: dict[str, list[float]] = {}
            for pid in pair_ids:
                if test_name not in perturbed[pid] or not cache[pid]["pitched"]:
                    continue
                if item.family == "beatshift" and not harmony_moves(pid, test_name):
                    continue
                found = recovered(pid, cache[pid]["perturbed"][test_name])
                if found is None:
                    continue
                value = found[0] if expected[0] == "transposition" else found[1]
                hits_by_track.setdefault(cache[pid]["track"], []).append(
                    1.0 if value == expected[1] else 0.0
                )
            if hits_by_track:
                hits = [h for values in hits_by_track.values() for h in values]
                report["tests"][test_name]["recovery"] = {
                    "what": expected[0],
                    "expected": expected[1],
                    "n": len(hits),
                    "accuracy": round(float(np.mean(hits)), 4),
                    "ci95": _bootstrap_ci(hits_by_track, rng),
                }

    # One figure per scorer and family: each pair contributes its mean win
    # over the family's tests, so a pair counts once however many tests it has.
    for label, (family, kind, reference) in POOLED.items():
        members = [
            n for n, item in catalogue.items() if item.family == family and item.kind == kind
        ]
        control = CONTROL_FOR.get(family)
        report["pooled"][label] = {}
        for name in scorers:
            by_track: dict[str, list[float]] = {}
            for pid in pair_ids:
                wins = []
                for test_name in members:
                    if test_name not in perturbed[pid]:
                        continue
                    if reference == "control":
                        if control not in perturbed[pid]:
                            continue
                        base = perturbed[pid][control][name]
                    else:
                        base = original[pid][name]
                    wins.append(_win(base - perturbed[pid][test_name][name]))
                if wins:
                    by_track.setdefault(cache[pid]["track"], []).append(float(np.mean(wins)))
            if by_track:
                values = [v for track_values in by_track.values() for v in track_values]
                report["pooled"][label][name] = {
                    "n": len(values),
                    "wins": round(float(np.mean(values)), 4),
                    "ci95": _bootstrap_ci(by_track, rng),
                }

    pitched_ids = [pid for pid in pair_ids if cache[pid]["pitched"]]
    untouched = [recovered(pid, cache[pid]["original"]) for pid in pitched_ids]
    untouched = [found for found in untouched if found is not None]
    if untouched:
        report["recovery_on_original"] = {
            "n": len(untouched),
            "transposition_is_zero": round(float(np.mean([t == 0 for t, _ in untouched])), 4),
            "delay_is_zero": round(float(np.mean([d == 0 for _, d in untouched])), 4),
        }
    return report


def _shard(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    index, count = (int(part) for part in text.split("/"))
    if not 0 <= index < count:
        raise argparse.ArgumentTypeError("shard must be i/n with 0 <= i < n")
    return index, count


def main() -> None:
    parser = argparse.ArgumentParser()
    stages = parser.add_subparsers(dest="stage", required=True)

    features = stages.add_parser("features")
    features.add_argument("--dataset", choices=["babyslakh", "musdb18hq"], required=True)
    features.add_argument("--root", type=pathlib.Path, required=True)
    features.add_argument("--store", type=pathlib.Path, required=True)
    features.add_argument("--models", default=",".join(signals.MODEL_NAMES))
    features.add_argument("--shard", type=_shard, help="i/n: every n-th track, starting at i")
    features.add_argument("--per-track", type=int, default=3)
    features.add_argument("--limit", type=int, help="stop after this many pairs (smoke runs)")

    report = stages.add_parser("report")
    report.add_argument("--store", type=pathlib.Path, required=True)
    report.add_argument("--output", type=pathlib.Path, required=True)
    report.add_argument("--dataset", default="")

    args = parser.parse_args()
    if args.stage == "features":
        if args.dataset == "babyslakh":
            pairs = datasets.babyslakh_pairs(args.root, per_track=args.per_track, shard=args.shard)
        else:
            pairs = musdb.musdb_pairs(args.root, shard=args.shard)
        if args.limit:
            pairs = (pair for _, pair in zip(range(args.limit), pairs))
        compute_features(pairs, signals.Embedders(tuple(args.models.split(","))), args.store)
        return

    result = analyse(load_store(args.store))
    result["dataset"] = args.dataset
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(result, indent=2))
    print(f"-> {args.output / 'report.json'}")


if __name__ == "__main__":
    main()
