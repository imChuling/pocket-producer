# Reproducing the ISMIR 2026 LBD Results

Every number in the paper is derived from versioned artifacts in
`artifacts/`. This document maps each claim to the script that produced it
and the command to re-run it. The mapping is enforced by
`research/check_paper_numbers.py` (151 assertions), which runs before every
PDF build; it expects the LaTeX source at `docs/ismir2026/lbd.tex`, which is
not distributed with this repository.

## Prerequisites

Python 3.11 or newer on macOS, Linux or Windows.

```bash
git clone https://github.com/imChuling/pocket-producer && cd pocket-producer
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -r backend/requirements.txt
```

That is enough for every result script (numpy and the `ranking` package; no
GPU, no torch). The scripts start from embedding files in
`research/data/fsld/`, which are **not in this repository**: they are derived
from other people's audio (the Freesound Loop Dataset) and nothing derived
from it is redistributed here. Build them once as described in the next
section, then:

```bash
python research/reproduce.py
```

re-runs every paper-facing script below into a scratch directory and prints
the largest numeric difference against the committed artifact for each one.
Expected wall-clock on a laptop CPU, once the embedding files exist:

| Step | Script | Time |
|------|--------|------|
| split | `make_heldout_split.py` | 10 s |
| fusion | `run_fusion.py` | about 10 min |
| ablation | `run_ablation.py` | about 5 min |
| heldout-laion | `run_heldout_correction.py --mode laion` | about 1.5 min |
| heldout-msclap | `run_heldout_correction.py --mode msclap` | about 1.5 min |
| weights | `export_fusion_weights.py` | about 1.5 min |

## Regenerating the embeddings from FSL10K

The paper's corpus is the Freesound Loop Dataset (FSL10K), Zenodo record
[3967852](https://zenodo.org/records/3967852), CC BY 4.0 as a collection
with a per-loop license inside. Download `FSL10K.zip` (8.8 GB) and
`annotations.zip` from that record into `research/data/fsld/`. Then install
the two audio models and run the chain:

```bash
python -m pip install -e "backend[research]"   # torch, msclap, laion-clap
# Linux without a GPU: install torch from https://download.pytorch.org/whl/cpu first

# 1. Per-loop license manifest (reads metadata.json out of the zip, needs network
#    only if the zip is not local)
python research/build_fsld_manifest.py

# 2. Embed the annotated, well-cut, research_ok subset (2,558 loops) in both spaces
python research/embed_fsld_subset.py --zip research/data/fsld/FSL10K.zip \
  --adapter msclap-2023 --out research/data/fsld/items.jsonl
python research/embed_fsld_subset.py --zip research/data/fsld/FSL10K.zip \
  --adapter laion-clap-music --out research/data/fsld/items_laion-clap-music.jsonl

# 3. Chroma for the harmonic signal (role_prompts.json is already tracked)
python research/extract_fsld_features.py --items research/data/fsld/items_laion-clap-music.jsonl

# 4. Pack-only corpus and the train side of the frozen split, in both spaces
python research/filter_pack_only.py --items research/data/fsld/items_laion-clap-music.jsonl \
  --output research/data/fsld/items_laion-clap-music_packonly.jsonl
python research/filter_pack_only.py --items research/data/fsld/items_laion-clap-music_packonly.jsonl \
  --train-only artifacts/heldout-split-packonly/split.json \
  --output research/data/fsld/items_laion-clap-music_packonly_train.jsonl
python research/filter_pack_only.py --items research/data/fsld/items.jsonl \
  --output research/data/fsld/items_msclap_packonly.jsonl
python research/filter_pack_only.py --items research/data/fsld/items_msclap_packonly.jsonl \
  --train-only artifacts/heldout-split-packonly/split.json \
  --output research/data/fsld/items_msclap_packonly_train.jsonl
```

Step 2 is the slow one: on a laptop CPU the model alone costs about 0.14 s per loop for
MS-CLAP and 0.68 s for LAION-CLAP, so with audio decoding expect roughly 20
minutes for the MS-CLAP pass and 45 minutes for the LAION-CLAP pass, after the
model weights download on first use. `embed_fsld_subset.py` is resumable, so
an interrupted run continues where it stopped.

**What to expect.** The corpus, split and every downstream computation are
deterministic, but the embedding step was not when the paper's files were
made: MS-CLAP picked its 7 s analysis window at random inside longer loops
(51% of the pack-only loops exceed 7 s), and LAION-CLAP truncates to 10 s the
same way. The MS-CLAP adapter has since been changed to crop the first 7 s,
so a regenerated MS-CLAP file is stable run to run, but neither regenerated
file is identical to the ones behind the paper, and `reproduce.py` will
report small differences (the conclusions, not the third decimal). The exact
files the paper used have the sha256 hashes listed in
`research/data/fsld/README.md`; I will share them with anyone who asks, for
non-commercial research use, since 263 of the 1,797 pack-only loops are
CC BY-NC or Sampling+ licensed.

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

The numbers above are reproducible from the `items_*.jsonl` embedding
files onward. The embedding step itself is not: `msclap` embeds a
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
