# MS-CLAP Sensitivity Re-Analysis Protocol v1

Status: **FROZEN at the commit that introduces this file.**

## Purpose

Sensitivity re-analysis of the pack-only five-signal fusion in the
production MS-CLAP embedding space. This reuses the frozen 484/121
held-out split from protocol-heldout-v2 and is explicitly **not**
confirmatory — the split has been evaluated once before under LAION-CLAP.

## Baselines (fixed, always reported together)

| Baseline | Signals | Weights |
|---|---|---|
| **rules** | tempo, key, tag_jaccard | hand-tuned: 0.353, 0.235, 0.412 (production-parallel, normalized) |
| **cosine** | audio_cos_mean | fixed 1.0 (no training) |
| **fusion-5sig** | audio_cos_mean, audio_cos_max, tempo, key, tag_jaccard | learned via source-weighted BPR |

Rules weights derive from the production rules-v1 ranker (tempo 0.30,
key 0.20, tag≈intent+novelty 0.35), renormalized to the three signals
available in FSLD items. The rules baseline receives **no training**.

## Training modifications (pre-fixed)

1. **Source-level weighting.** Each source's gradient contribution is
   divided by the number of examples from that source, so large packs
   do not dominate the BPR loss.

2. **hard_similar upweight = 2.0.** Each hard_similar negative pair's
   gradient is multiplied by 2.0 relative to easy and hard_tempo_key.
   This is fixed before any run and cannot be tuned post-hoc.

3. All other hyperparameters unchanged from protocol-heldout-v2:
   Adam, lr=0.05, 300 epochs, val_fraction=0.25, 5 seeds.

## Data

- Items: `research/data/fsld/items_msclap_packonly.jsonl` (1,797 items,
  605 pack sources, MS-CLAP 2023 1024-dim embeddings)
- Split: `artifacts/heldout-split-packonly/split.json` (484 train /
  121 held-out, seed 20260810)
- Pairs: `build_weak_pairs` with PAIR_SEED=20260725, CONTEXT_MIN=2

## Design

1. **Development (train side only).** Source-grouped 5-fold CV
   (val_fraction=0.25, 5 seeds). Report per-seed and mean±std for
   each baseline × each negative regime (easy, hard_tempo_key,
   hard_similar, overall).

2. **Held-out (single run).** Retrain fusion on full train side (5
   seeds, same hyperparameters + source weighting + hs upweight),
   evaluate once on 121 held-out sources. **No re-runs permitted.**

3. **Uncertainty.** Source-grouped bootstrap CIs (10,000 draws,
   α=0.05, joint source resampling shared across seeds).

4. **LOSO replication.** Leave-one-signal-out on held-out to check
   whether regime-dependent contributions replicate in MS-CLAP space.

## Reporting

All results reported regardless of outcome. Per-regime breakdowns
mandatory. The three baselines always appear side-by-side.

## Labeling

This entire run is a **sensitivity re-analysis**: same split, same
protocol structure, different embedding space. The paper must label it
as such and must not claim confirmatory status.

## Known limitations

- The held-out split was previously evaluated under LAION-CLAP;
  second use under MS-CLAP is a sensitivity check, not independent.
- Signal set and hyperparameters designed on the LAION-CLAP corpus.
- MS-CLAP produces 1024-dim vectors vs LAION-CLAP 512-dim; the
  cosine geometry differs.
