# Reproducing the ISMIR 2026 LBD Results

Every number in the paper is derived from versioned artifacts in
`artifacts/`. This document maps each claim to the script that produced it
and the command to re-run it. The mapping is enforced by
`research/check_paper_numbers.py` (151 assertions), which runs before every
PDF build; it expects the LaTeX source at `docs/ismir2026/lbd.tex`, which is
not distributed with this repository.

## Prerequisites

Python 3.11 or newer on macOS, Linux or Windows. Everything the result chain
needs is in `backend/requirements.txt` (numpy and the `ranking` package; no
GPU, no torch).

```bash
git clone https://github.com/imChuling/pocket-producer && cd pocket-producer
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -r backend/requirements.txt
python research/fetch_embeddings.py  # 72 MB bundle, sha256-verified
```

`fetch_embeddings.py` downloads the exact embedding files the paper was
computed from (the embedding step itself is not deterministic, see below)
into `research/data/fsld/` and checks every file against the manifest
shipped inside the bundle:

| File | Contents |
|------|----------|
| `items_laion-clap-music.jsonl` | LAION-CLAP Music embeddings, full mixed-label corpus (2,558 items) |
| `items_laion-clap-music_packonly.jsonl` | pack-only corpus (1,797 items, 605 packs) |
| `items_laion-clap-music_packonly_train.jsonl` | train side of the frozen split (484 sources) |
| `items_msclap_packonly.jsonl` / `..._train.jsonl` | same corpus in MS-CLAP 2023 space |
| `items_mert_packonly.jsonl` | same corpus in MERT-v1-95M space (supporting column) |
| `chroma.jsonl` | 12-dim chroma per item, for the harmonic signal |
| `manifest.jsonl` | per-item Freesound id, uploader, pack and license |

The files are feature vectors, not audio. The audio itself (FSL10K, Zenodo
record 3967852) is not redistributed; 263 of the 1,797 pack-only items are
CC BY-NC or Sampling+ and their vectors are included for non-commercial
reproduction only, with the license of every item in `manifest.jsonl`.

### One command

```bash
python research/reproduce.py
```

re-runs every paper-facing script below into a scratch directory and prints
the largest numeric difference against the committed artifact for each one
(tolerance 1e-6). The same check runs on Linux, macOS and Windows runners
from the `reproduce` workflow in `.github/workflows/`. Expected wall-clock on
a laptop CPU:

| Step | Script | Time |
|------|--------|------|
| split | `make_heldout_split.py` | 10 s |
| fusion | `run_fusion.py` | about 10 min |
| ablation | `run_ablation.py` | about 5 min |
| heldout-laion | `run_heldout_correction.py --mode laion` | about 1.5 min |
| heldout-msclap | `run_heldout_correction.py --mode msclap` | about 1.5 min |
| weights | `export_fusion_weights.py` | about 1.5 min |

The commands below are what `reproduce.py` runs, one table at a time. Run
them from the repository root with the virtual environment activated.

## Corpus and split (§3)

Pack-only filtering (drops `user:`-grouped sources; keeps true Freesound
packs → 1,797 items, 605 packs):

```bash
python research/filter_pack_only.py \
  --items research/data/fsld/items_laion-clap-music.jsonl \
  --output research/data/fsld/items_laion-clap-music_packonly.jsonl
```

Frozen held-out split (seed 20260810, 121 held-out / 484 train sources;
committed before any evaluation touched it):

```bash
python research/make_heldout_split.py \
  --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
  --seed 20260810 --fraction 0.2 \
  --output artifacts/heldout-split-packonly/split.json
```

## Dev-set results (§3: cosine 0.929 / 0.8136, fusion 0.925 / 0.8133)

Five-signal fusion vs frozen cosine, 5 source-grouped splits on the
train side only:

```bash
python research/run_fusion.py \
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
python research/run_ablation.py \
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
python research/run_heldout_correction.py \
  --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
  --split artifacts/heldout-split-packonly/split.json \
  --output artifacts/heldout-eval-correction \
  --mode laion

# MS-CLAP + source-weighted BPR column
python research/run_heldout_correction.py \
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
python research/export_fusion_weights.py \
  --items research/data/fsld/items_msclap_packonly_train.jsonl \
  --output artifacts/fusion-deploy/weights.json
```

## Supporting artifacts (not cited in the paper body)

| Artifact | Script | Purpose |
|----------|--------|---------|
| `artifacts/factorial/factorial.json` | `run_factorial.py` | 2×2 representation × training decomposition (dev side only) |
| `artifacts/heldout-eval-packonly/` | `run_heldout_eval.py` | superseded first held-out run (kept for the corrective-disclosure audit trail) |
| `artifacts/human-signal-alignment/alignment.json` | `human_signal_alignment.py` | pilot signal-alignment analysis (removed from the paper; raw vote matrix unavailable) |
| `artifacts/ablation-7sig-packonly/ablation.json` | `run_ablation_7sig.py` | 7-signal LOSO on the pack-only train side; role_gap and harmonic add nothing over fusion-5sig |
| `artifacts/standardize-check/` | `run_standardize_check.py` | per-signal standardization before BPR; worse on both LAION and MS-CLAP dev splits, not adopted |
| `artifacts/keymask-check/keymask_msclap.json` | `run_keymask_check.py` | train/serve key mismatch: serving the shipped weights with key = 0 costs nothing on dev (+0.5 pp overall); retraining with key masked recovers +0.02 pp, so the shipped weights stay |
| `artifacts/heldout-eval-mert/sensitivity.json` | `embed_mert_from_previews.py` + `run_heldout_correction.py --mode mert` | third representation column (MERT-v1-95M from Freesound preview MP3s); fusion advantage persists but the MERT cosine baseline is weaker (0.848 overall) |
| `artifacts/heldout-eval-decoupled/sensitivity.json` | `run_heldout_correction.py --mode decoupled --items-mining items_mert_packonly.jsonl` | hard_similar mined in MERT space, signals scored in LAION-CLAP space: CLAP cosine on hard_similar rises to 0.957 and the fusion advantage shrinks to +1.4 pp, so most of the CLAP-mined hard_similar gain comes from mining negatives in the scored space |
| `artifacts/human-eval-v1/power_sim.json` | `power_sim_human_v1.py` | power simulation for the pre-registered listening study (`prereg_human_v1.md`), driven by the 17 discordant-capable pairs in `data/listening_test/pairs.json` |
| `artifacts/fusion-feedback/weights.json` (once data exists) | `finetune_from_feedback.py` | fusion weights fine-tuned on logged musician decisions (`ranking_requests.candidate_signals` + `ranking_feedback`), warm-started from the deployed weights |

## Embedding-stage determinism (caveat)

The numbers above are reproducible from the distributed `items_*.jsonl`
embedding files onward. The embedding step itself is not: `msclap` embeds a
7 s window and picks it at random from longer clips (`CLAPWrapper.py`,
`random.randrange`), and `embed_fsld_subset.py` set no seed. 51% of the
pack-only loops exceed 7 s (27% exceed 14 s), so re-running
`embed_fsld_subset.py` yields different vectors for those items. LAION-CLAP
without fusion truncates to 10 s the same way. The deployed adapter now
crops to the first 7 s before calling the model (`ranking/adapters/msclap.py`),
so online session embeddings are deterministic; the research files were
produced before that change and are kept as-is.

## Verification

Number consistency check (151 assertions, paper ↔ artifacts):

```bash
python research/check_paper_numbers.py
```

Unit tests (signal functions):

```bash
python -m pytest backend/tests/ranking -q
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
