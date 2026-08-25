# Reproducing the ISMIR 2026 LBD Results

Every number in the paper (`docs/ismir2026/lbd.tex`) is derived from
versioned artifacts in `artifacts/`. This document maps each claim to the
script that produced it and the command to re-run it. The mapping is
enforced by `research/check_paper_numbers.py` (151 assertions), which runs
before every PDF build.

## Prerequisites

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Embedding files live in `research/data/fsld/` (~200 MB total):

| File | Contents |
|------|----------|
| `items_laion-clap-music.jsonl` | LAION-CLAP Music embeddings, full mixed-label corpus |
| `items_laion-clap-music_packonly.jsonl` | pack-only corpus (1,797 items, 605 packs) |
| `items_laion-clap-music_packonly_train.jsonl` | train side of the frozen split (484 sources) |
| `items_msclap_packonly.jsonl` / `..._train.jsonl` | same corpus in MS-CLAP 2023 space |

All commands below run from the repo root with
`backend/.venv/bin/python`.

## Corpus and split (§3)

Pack-only filtering (drops `user:`-grouped sources; keeps true Freesound
packs → 1,797 items, 605 packs):

```bash
backend/.venv/bin/python research/filter_pack_only.py \
  --items research/data/fsld/items_laion-clap-music.jsonl \
  --output research/data/fsld/items_laion-clap-music_packonly.jsonl
```

Frozen held-out split (seed 20260810, 121 held-out / 484 train sources;
committed before any evaluation touched it):

```bash
backend/.venv/bin/python research/make_heldout_split.py \
  --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
  --seed 20260810 --fraction 0.2 \
  --output artifacts/heldout-split-packonly/split.json
```

## Dev-set results (§3: cosine 0.929 / 0.8136, fusion 0.925 / 0.8133)

Five-signal fusion vs frozen cosine, 5 source-grouped splits on the
train side only:

```bash
backend/.venv/bin/python research/run_fusion.py \
  --items research/data/fsld/items_laion-clap-music_packonly_train.jsonl \
  --output artifacts/fusion-packonly
```

## Observations (§4)

### Label sensitivity (+4.0 pp under mixed labels)

The earlier mixed-label corpus (same-uploader grouping, 949 sources) is
preserved as `artifacts/fusion-7sig/fusion.json`, produced by the same
`run_fusion.py` on `items_laion-clap-music.jsonl`. The paper cites its
hard_similar delta to show the gain vanishes under pack-only labels.

### Regime dependence (LOSO: tempo −0.96 pp / +0.68 pp)

```bash
backend/.venv/bin/python research/run_ablation.py \
  --items research/data/fsld/items_laion-clap-music_packonly_train.jsonl \
  --output artifacts/ablation-packonly
```

### Held-out uncertainty (Table 1)

Corrective protocol (`protocol-heldout-correction-v1.md`): retrain on all
484 train sources, evaluate once on the held-out split. The paper labels
these results exploratory because they postdate an initial
training-protocol mismatch.

```bash
# LAION-CLAP column
backend/.venv/bin/python research/run_heldout_correction.py \
  --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
  --split artifacts/heldout-split-packonly/split.json \
  --output artifacts/heldout-eval-correction \
  --mode laion

# MS-CLAP + source-weighted BPR column
backend/.venv/bin/python research/run_heldout_correction.py \
  --items research/data/fsld/items_msclap_packonly.jsonl \
  --split artifacts/heldout-split-packonly/split.json \
  --output artifacts/msclap-sensitivity-correction \
  --mode msclap
```

Bootstrap CIs (10,000 source-level resamples, mean over 5 seeds) are
computed inside these scripts.

## Deployed weights (§2.4)

Trains fusion-5sig on the full pack-only train side in MS-CLAP space
with source-weighted BPR and exports the shipped weights:

```bash
backend/.venv/bin/python research/export_fusion_weights.py \
  --items research/data/fsld/items_msclap_packonly_train.jsonl \
  --output artifacts/fusion-deploy/weights.json
```

## Supporting artifacts (not cited in the paper body)

| Artifact | Script | Purpose |
|----------|--------|---------|
| `artifacts/factorial/factorial.json` | `run_factorial.py` | 2×2 representation × training decomposition (dev side only) |
| `artifacts/heldout-eval-packonly/` | `run_heldout_eval.py` | superseded first held-out run (kept for the corrective-disclosure audit trail) |
| `artifacts/human-signal-alignment/alignment.json` | `human_signal_alignment.py` | pilot signal-alignment analysis (removed from the paper; raw vote matrix unavailable) |

## Verification

Number consistency check (151 assertions, paper ↔ artifacts):

```bash
python research/check_paper_numbers.py
```

Unit tests (signal functions):

```bash
backend/.venv/bin/python -m pytest backend/tests/ranking/ -v
```

Build the paper (runs the number check first):

```bash
docs/ismir2026/build.sh
```

## Artifact inventory (paper-facing)

| Artifact | Source script | Paper reference |
|----------|---------------|-----------------|
| `artifacts/heldout-split-packonly/split.json` | `make_heldout_split.py` | §3 (605/484/121, seed 20260810) |
| `artifacts/fusion-packonly/fusion.json` | `run_fusion.py` | §3 dev-set accuracies |
| `artifacts/fusion-7sig/fusion.json` | `run_fusion.py` (mixed labels) | §4 label sensitivity (+4.0 pp) |
| `artifacts/ablation-packonly/ablation.json` | `run_ablation.py` | §4 regime dependence (LOSO) |
| `artifacts/heldout-eval-correction/sensitivity.json` | `run_heldout_correction.py --mode laion` | Table 1, LAION column |
| `artifacts/msclap-sensitivity-correction/sensitivity.json` | `run_heldout_correction.py --mode msclap` | Table 1, MS-CLAP sw-BPR column |
| `artifacts/fusion-deploy/weights.json` | `export_fusion_weights.py` | §2.4 deployment configuration |
