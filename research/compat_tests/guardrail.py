"""Behavioural guardrail for a set of linear ranking weights.

A weight vector over named signals is scored on a stored behavioural-test
feature set and compared with the deployed five-signal fusion on the
protocol's primary endpoints (P1 to P5) and on gain invariance:

- an endpoint the baseline passes (95% interval above 0.5) must still pass;
- the gain-6dB win rate may not sit further from 0.5 than the baseline's.

Statistics follow run_behavioral: per-pair score differences, a tie counts
as half a win, track-level bootstrap intervals. Each endpoint is resampled
with the same seeded generator for both weight sets, so the two intervals
use identical resamples (they differ from the report's intervals, which
share one generator across all summaries; the win rates are identical).

  python -m research.compat_tests.guardrail --weights candidate.json \
    --store research/data/compat/musdb18_v1 --output verdict.json

The weights file has the fusion artifact's shape: {"signals": [...], "weights": [...]}.
"""

import argparse
import dataclasses
import json
import pathlib
import pickle
from collections.abc import Iterable, Iterator

import numpy as np

from . import perturb, progression, run_behavioral, signals

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASELINE_WEIGHTS = ROOT / "artifacts" / "fusion-deploy" / "weights.json"
DEFAULT_STORE = ROOT / "research" / "data" / "compat" / "musdb18_v1"

# Signal names used by the deployed ranker and its logs, as behavioural-test
# scorers. Key and tags are zero online (the host exposes no key and stems
# carry no tags), so they contribute nothing here, as in fusion5_online.
ALIASES = {
    "audio_cos_mean": "clap_cos_mean",
    "audio_cos_max": "clap_cos_max",
    "tempo": "tempo",
    "key": None,
    "tag_jaccard": None,
}
GAIN_TEST = "gain-6dB"
ENDPOINTS = ("P1", "P2", "P3", "P4", "P5")


@dataclasses.dataclass(frozen=True)
class WeightSet:
    signals: tuple[str, ...]
    weights: tuple[float, ...]

    @classmethod
    def from_file(cls, path: pathlib.Path | str) -> "WeightSet":
        data = json.loads(pathlib.Path(path).read_text())
        return cls.of(data["signals"], data["weights"])

    @classmethod
    def of(cls, names: Iterable[str], weights: Iterable[float]) -> "WeightSet":
        names, weights = tuple(names), tuple(float(w) for w in weights)
        if len(names) != len(weights):
            raise ValueError(f"{len(names)} signals but {len(weights)} weights")
        for name in names:
            if name not in ALIASES and name not in signals.SCORER_NAMES:
                raise ValueError(f"unknown signal {name!r}")
        return cls(names, weights)

    def components(self) -> set[str]:
        return {ALIASES.get(n, n) for n in self.signals if ALIASES.get(n, n) is not None}

    def score(self, component_scores: dict[str, float]) -> float:
        total = 0.0
        for name, weight in zip(self.signals, self.weights):
            component = ALIASES.get(name, name)
            if component is not None:
                total += weight * component_scores[component]
        return total


def _tests_needed() -> dict[str, perturb.Perturbation]:
    catalogue = {item.name: item for item in perturb.catalogue()}
    wanted = {}
    for label, (family, kind, _) in run_behavioral.POOLED.items():
        if label in ("pitch_vs_control", "varispeed"):
            wanted.update(
                {n: i for n, i in catalogue.items() if i.family == family and i.kind == kind}
            )
    for name in ("pitch_roundtrip", "beatshift4", "beatshift0.37", GAIN_TEST):
        if name in catalogue:
            wanted[name] = catalogue[name]
    return wanted


def iter_store(store: pathlib.Path) -> Iterator[dict]:
    """Stored pairs one at a time; the full store never sits in memory."""
    for path in sorted(p for p in store.glob("*.pkl") if not p.name.startswith("._")):
        yield pickle.loads(path.read_bytes())


def _harmony_moves(entry: dict, test_name: str) -> bool:
    before, after = entry["original"], entry["perturbed"].get(test_name)
    if after is None or before.beat_chroma is None or after.beat_chroma is None:
        return False
    fit = progression.aligned_fit(before.beat_chroma, after.beat_chroma)
    return fit > 0 and 1.0 - fit >= run_behavioral.MIN_HARMONIC_CHANGE


def collect(entries: Iterable[dict], components: set[str]) -> dict:
    """Component scores for every needed clip of every pair, plus what P1 needs."""
    fusion = signals.load_fusion_weights()
    embedders = signals.Embedders(("cocola",)) if "cocola" in components else None
    tests = _tests_needed()
    pairs: dict[str, dict] = {}
    slim: dict[str, dict] = {}

    def comp(entry, features):
        scores = signals.score_all(
            entry["context_mix"], entry["regions"], features, fusion, embedders
        )
        missing = components - scores.keys()
        if missing:
            raise ValueError(f"store has no features for {sorted(missing)}")
        return {name: scores[name] for name in components}

    for entry in entries:
        pid = entry["pair_id"]
        pairs[pid] = {
            "track": entry["track"],
            "pitched": entry["pitched"],
            "original": comp(entry, entry["original"]),
            "perturbed": {
                name: comp(entry, feats)
                for name, feats in entry["perturbed"].items()
                if name in tests
            },
            "harmony_moves": entry["pitched"] and _harmony_moves(entry, "beatshift4"),
        }
        slim[pid] = {
            "track": entry["track"],
            "grid": entry["grid"],
            "original": entry["original"],
            "original_frames": entry.get("original_frames"),
            "context_mix": entry["context_mix"],
            "regions": entry["regions"],
        }

    for pid, candidates in run_behavioral.foreign_candidates(slim).items():
        pairs[pid]["foreign"] = [comp(slim[pid], c) for c in candidates.values()]
    return {"pairs": pairs, "tests": tests}


def _summarise(values_by_track: dict[str, list[float]]) -> dict | None:
    if not values_by_track:
        return None
    rng = np.random.default_rng(run_behavioral.BOOTSTRAP_SEED)
    values = [v for vs in values_by_track.values() for v in vs]
    return {
        "n": len(values),
        "wins": round(float(np.mean(values)), 4),
        "ci95": run_behavioral._bootstrap_ci(values_by_track, rng),
    }


def endpoints(collected: dict, weights: WeightSet) -> dict[str, dict | None]:
    """Win rates and intervals on P1 to P5 and the gain test for one weight set."""
    pairs, tests = collected["pairs"], collected["tests"]
    pitch = [n for n, i in tests.items() if i.family == "pitch" and i.kind == "directional"]
    varispeed = [n for n, i in tests.items() if i.family == "varispeed"]
    win = run_behavioral._win

    def per_pair(pid, test, reference="original"):
        p = pairs[pid]
        if test not in p["perturbed"]:
            return None
        base = p["original"] if reference == "original" else p["perturbed"].get(reference)
        if base is None:
            return None
        return win(weights.score(base) - weights.score(p["perturbed"][test]))

    buckets: dict[str, dict[str, list[float]]] = {k: {} for k in (*ENDPOINTS, "gain")}
    for pid, p in pairs.items():
        track = p["track"]
        mine = weights.score(p["original"])
        for other in p.get("foreign", []):
            buckets["P1"].setdefault(track, []).append(win(mine - weights.score(other)))
        for label, members, reference in (
            ("P2", pitch, "pitch_roundtrip"),
            ("P3", varispeed, "original"),
        ):
            wins = [w for t in members if (w := per_pair(pid, t, reference)) is not None]
            if wins:
                buckets[label].setdefault(track, []).append(float(np.mean(wins)))
        if p["harmony_moves"] and (w := per_pair(pid, "beatshift4")) is not None:
            buckets["P4"].setdefault(track, []).append(w)
        for label, test in (("P5", "beatshift0.37"), ("gain", GAIN_TEST)):
            if (w := per_pair(pid, test)) is not None:
                buckets[label].setdefault(track, []).append(w)
    return {label: _summarise(values) for label, values in buckets.items()}


def _passes(summary: dict | None) -> bool:
    return bool(summary) and summary["ci95"][0] > 0.5


def decide(baseline: dict, candidate: dict) -> dict:
    """Accept unless a baseline pass is lost or gain sensitivity grows."""
    reasons = []
    for label in ENDPOINTS:
        if _passes(baseline.get(label)) and not _passes(candidate.get(label)):
            c = candidate.get(label)
            got = f"{c['wins']} {c['ci95']}" if c else "no data"
            reasons.append(
                f"{label}: baseline passes ({baseline[label]['wins']} "
                f"{baseline[label]['ci95']}), candidate does not ({got})"
            )
    base_gain, cand_gain = baseline.get("gain"), candidate.get("gain")
    if base_gain and cand_gain:
        if abs(cand_gain["wins"] - 0.5) > abs(base_gain["wins"] - 0.5) + 1e-9:
            reasons.append(
                f"gain-6dB: candidate {cand_gain['wins']} is further from 0.5 than "
                f"baseline {base_gain['wins']}"
            )
    elif base_gain and not cand_gain:
        reasons.append("gain-6dB: no data for the candidate")
    return {"verdict": "reject" if reasons else "accept", "reasons": reasons}


def check(
    candidate: WeightSet,
    entries: Iterable[dict],
    baseline: WeightSet | None = None,
) -> dict:
    baseline = baseline or WeightSet.from_file(BASELINE_WEIGHTS)
    collected = collect(entries, candidate.components() | baseline.components())
    base, cand = endpoints(collected, baseline), endpoints(collected, candidate)
    result = decide(base, cand)
    result.update(
        {
            "n_pairs": len(collected["pairs"]),
            "baseline": {"weights": dataclasses.asdict(baseline), "endpoints": base},
            "candidate": {"weights": dataclasses.asdict(candidate), "endpoints": cand},
            "rule": (
                "every endpoint the baseline passes must still pass; the gain-6dB win "
                "rate may not be further from 0.5 than the baseline's"
            ),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Behavioural guardrail for ranking weights")
    parser.add_argument("--weights", required=True, type=pathlib.Path)
    parser.add_argument("--store", type=pathlib.Path, default=DEFAULT_STORE)
    parser.add_argument("--baseline", type=pathlib.Path, default=BASELINE_WEIGHTS)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    if not args.store.is_dir():
        parser.error(f"feature store not found: {args.store}")
    result = check(
        WeightSet.from_file(args.weights),
        iter_store(args.store),
        WeightSet.from_file(args.baseline),
    )
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(json.dumps({"verdict": result["verdict"], "reasons": result["reasons"]}, indent=2))
    return 0 if result["verdict"] == "accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
