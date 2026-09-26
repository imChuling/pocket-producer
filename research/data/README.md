# Research Data Provenance

This directory stores only metadata, manifests, and fixture IDs. No participant audio or unauthorized audio is stored here.

## Rules

1. Every data file must answer: source, license, collection date, processing script, `sha256`.
2. Participant data: user IDs are one-way hashed (`participant_hash`). No email, OAuth token, or raw project title is stored.
3. Public weak-supervision data (e.g. FSLD): per-item license verification required. "Creative Commons" is not treated as a blanket license; only subsets that permit research processing are used.
4. Time-stretched, pitch-shifted, or duplicate-hash variants of the same audio must not cross train/val/test split boundaries.
5. Split policy: public weak data by source track/pack/uploader; human study by participant and project; personal feedback by time.
6. `golden_pairs.jsonl` contains only synthetic, self-owned, or explicitly authorized fixtures; see `research/annotation-schema.md`.

## Directory layout

```text
research/data/
├── README.md            # this file
├── pocketbench.jsonl    # PocketBench v1 manifest (includes dataset_hash)
├── weak_pairs.jsonl     # Layer A weak-supervision pairs
├── pairs.jsonl          # Layer B explicit pairwise annotations
└── heldout.jsonl        # frozen test set (do not evaluate before unsealing)
```

All evaluation artifacts are written to `artifacts/` (large files are git-ignored), but `dataset_hash` and `metrics.json` must be reproducible.
