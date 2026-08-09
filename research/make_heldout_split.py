"""Generate a source-level held-out split and freeze it as an artifact.

Samples a fraction of source_ids uniformly at random with a fixed seed,
writes split.json with the held-out id list and its SHA-256, so the
split can be committed BEFORE any evaluation touches it.

Usage:
  python research/make_heldout_split.py \
    --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
    --seed 20260810 --fraction 0.2 \
    --output artifacts/heldout-split-packonly/split.json
"""

import argparse
import hashlib
import json
import pathlib

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--fraction", type=float, default=0.2)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sources = set()
    with open(args.items) as f:
        for line in f:
            if line.strip():
                sources.add(json.loads(line)["source_id"])
    sources = sorted(sources)

    rng = np.random.default_rng(args.seed)
    n_heldout = round(len(sources) * args.fraction)
    heldout = sorted(rng.choice(sources, size=n_heldout, replace=False).tolist())

    sha = hashlib.sha256("\n".join(heldout).encode()).hexdigest()

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "split_seed": args.seed,
        "split_fraction": args.fraction,
        "n_total_sources": len(sources),
        "n_heldout_sources": len(heldout),
        "n_train_sources": len(sources) - len(heldout),
        "heldout_source_ids": heldout,
        "sha256_heldout_ids": sha,
    }, indent=2))

    print(f"{len(sources)} sources -> {len(heldout)} held-out, "
          f"{len(sources) - len(heldout)} train")
    print(f"sha256: {sha}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
