"""Filter an items JSONL to pack-only sources.

FSLD manifest rows fall back to `user:<username>` as source_id when the
sound has no pack.  Same-uploader grouping is a weaker proxy for shared
production context than pack co-membership, so the pack-only corpus
drops every `user:`-grouped source.

Optionally also restricts to a set of source_ids from a split file
(--train-only), so development experiments can run strictly on the
train side of a frozen held-out split.

Usage:
  python research/filter_pack_only.py \
    --items research/data/fsld/items_laion-clap-music.jsonl \
    --output research/data/fsld/items_laion-clap-music_packonly.jsonl

  python research/filter_pack_only.py \
    --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
    --train-only artifacts/heldout-split-packonly/split.json \
    --output research/data/fsld/items_laion-clap-music_packonly_train.jsonl
"""

import argparse
import json
import pathlib


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--train-only",
        help="split.json path; keep only sources NOT in heldout_source_ids",
    )
    args = parser.parse_args()

    drop_ids = set()
    if args.train_only:
        with open(args.train_only) as f:
            drop_ids = set(json.load(f)["heldout_source_ids"])

    n_in = n_out = 0
    sources = set()
    out_path = pathlib.Path(args.output)
    with open(args.items) as fin, out_path.open("w") as fout:
        for line in fin:
            if not line.strip():
                continue
            n_in += 1
            row = json.loads(line)
            sid = row["source_id"]
            if sid.startswith("user:"):
                continue
            if sid in drop_ids:
                continue
            fout.write(line)
            n_out += 1
            sources.add(sid)

    print(f"{n_in} items in -> {n_out} items out, {len(sources)} sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
