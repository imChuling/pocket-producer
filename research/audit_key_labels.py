"""Key label quality audit (protocol-key-audit-v1 Step A).

Estimates keys from audio via CQT chroma + Krumhansl-Schmuckler template
matching, then compares against FSL10K annotation keys. Reports exact
agreement, relative-key agreement, and fifth-neighbor agreement.

Usage:
  backend/.venv/bin/python research/audit_key_labels.py \
    --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
    --zip   research/data/fsld/FSL10K.zip \
    --output artifacts/key-audit/key_audit.json
"""

import argparse
import json
import pathlib
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from ranking.features import _parse_key, normalize_key
from ranking.harmonic_probe import CHROMA_BINS, SEMITONE_NAMES, chroma_from_audio

# Krumhansl-Schmuckler key profiles (normalized)
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_PROFILES = []
for _pc in range(CHROMA_BINS):
    _PROFILES.append((np.roll(_KS_MAJOR, _pc), f"{SEMITONE_NAMES[_pc].lower()} major"))
    _PROFILES.append((np.roll(_KS_MINOR, _pc), f"{SEMITONE_NAMES[_pc].lower()} minor"))

SAMPLE_SIZE = 100
SAMPLE_SEED = 20260825
SAMPLE_RATE = 22050


def estimate_key(chroma_vector: list[float]) -> str:
    c = np.asarray(chroma_vector)
    if np.linalg.norm(c) < 1e-10:
        return "unknown"
    best_corr = -2.0
    best_key = "unknown"
    for profile, name in _PROFILES:
        r = float(np.corrcoef(c, profile)[0, 1])
        if r > best_corr:
            best_corr = r
            best_key = name
    return best_key


def stratified_sample(items, rng, n=SAMPLE_SIZE):
    by_key = defaultdict(list)
    for item in items:
        k = normalize_key(item.get("key"))
        if k is not None and _parse_key(k) is not None:
            by_key[k].append(item)
    cells = sorted(by_key.keys())
    per_cell = max(1, n // len(cells)) if cells else 0
    sampled = []
    for key_class in cells:
        pool = by_key[key_class]
        rng.shuffle(pool)
        sampled.extend(pool[:per_cell])
    if len(sampled) < n:
        remaining = [i for i in items if i not in sampled and
                     normalize_key(i.get("key")) is not None and
                     _parse_key(normalize_key(i.get("key"))) is not None]
        rng.shuffle(remaining)
        sampled.extend(remaining[:n - len(sampled)])
    return sampled[:n]


def _agreement_level(annotation: str, estimated: str):
    ap = _parse_key(annotation)
    ep = _parse_key(estimated)
    if ap is None or ep is None:
        return "unparseable"
    if annotation == estimated:
        return "exact"
    a_pc, a_mode = ap
    e_pc, e_mode = ep
    if a_mode != e_mode:
        if a_mode == "major" and (a_pc - 3) % 12 == e_pc:
            return "relative"
        if e_mode == "major" and (e_pc - 3) % 12 == a_pc:
            return "relative"
    interval = abs(a_pc - e_pc) % 12
    if a_mode == e_mode and interval in (5, 7):
        return "fifth"
    return "wrong"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--output", default="artifacts/key-audit/key_audit.json")
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE)
    args = parser.parse_args()

    import librosa

    items = [json.loads(l) for l in open(args.items) if l.strip()]
    print(f"loaded {len(items)} items")
    keyed = [i for i in items if normalize_key(i.get("key")) is not None]
    print(f"{len(keyed)} have parseable key annotations")

    rng = np.random.default_rng(SAMPLE_SEED)
    sample = stratified_sample(keyed, rng, n=args.sample_size)
    print(f"sampled {len(sample)} items for audit")

    archive = zipfile.ZipFile(args.zip)
    wav_by_id = {}
    for name in archive.namelist():
        base = pathlib.Path(name).name
        if name.endswith(".wav") and "_" in base:
            wav_by_id.setdefault(base.split("_", 1)[0], name)

    results = []
    for item in sample:
        fsid = item["item_id"].split(":")[-1]
        member = wav_by_id.get(fsid)
        if member is None:
            continue
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            f.write(archive.read(member))
            f.flush()
            waveform, _ = librosa.load(f.name, sr=SAMPLE_RATE, mono=True, duration=30.0)
        chroma = chroma_from_audio(waveform, SAMPLE_RATE)
        est = estimate_key(chroma)
        ann = normalize_key(item["key"])
        level = _agreement_level(ann, est)
        results.append({
            "item_id": item["item_id"],
            "annotation": ann,
            "estimated": est,
            "agreement": level,
        })

    counts = Counter(r["agreement"] for r in results)
    n = len(results)
    exact_rate = counts.get("exact", 0) / n if n else 0
    relative_rate = (counts.get("exact", 0) + counts.get("relative", 0)) / n if n else 0
    fifth_rate = (counts.get("exact", 0) + counts.get("relative", 0) +
                  counts.get("fifth", 0)) / n if n else 0

    confusion = defaultdict(Counter)
    for r in results:
        if r["agreement"] not in ("exact",):
            confusion[r["annotation"]][r["estimated"]] += 1

    report = {
        "protocol": "research/protocol-key-audit-v1.md",
        "n_audited": n,
        "sample_seed": SAMPLE_SEED,
        "exact_agreement": round(exact_rate, 4),
        "relative_agreement": round(relative_rate, 4),
        "fifth_agreement": round(fifth_rate, 4),
        "level_counts": dict(counts),
        "decision_rule": (
            "exact < 0.60 supports H-label; >= 0.80 weakens H-label; "
            "between is inconclusive"
        ),
        "confusion_non_exact": {
            k: dict(v) for k, v in sorted(confusion.items())
        },
        "per_item": results,
    }

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"\nn={n}, exact={exact_rate:.1%}, "
          f"+relative={relative_rate:.1%}, +fifth={fifth_rate:.1%}")
    for level in ("exact", "relative", "fifth", "wrong", "unparseable"):
        print(f"  {level}: {counts.get(level, 0)}")
    if exact_rate < 0.60:
        print("\nDecision: exact < 60% -> SUPPORTS H-label (annotation noise)")
    elif exact_rate >= 0.80:
        print("\nDecision: exact >= 80% -> WEAKENS H-label")
    else:
        print("\nDecision: inconclusive (60-80%)")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
