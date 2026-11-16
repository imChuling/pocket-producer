# 2x2 Factorial: Representation x Training Protocol v1

Status: **FROZEN at the commit that introduces this file.**

## Purpose

Disentangle the contribution of embedding space vs training recipe
to the +9.2 pp hard_similar advantage observed in the MS-CLAP
sensitivity re-analysis. The sensitivity run changed both the
representation (LAION-CLAP -> MS-CLAP) and the training objective
(uniform BPR -> source-weighted BPR with hard_similar x2.0)
simultaneously; this factorial separates main effects from
interaction.

## Design

2x2 factorial on the train side only (484 sources, protocol-heldout-v2
split). No held-out sources are touched.

| Condition | Embedding | Training |
|---|---|---|
| A | LAION-CLAP (512-dim) | uniform BPR |
| B | LAION-CLAP (512-dim) | source-weighted BPR (hs x2.0) |
| C | MS-CLAP (1024-dim) | uniform BPR |
| D | MS-CLAP (1024-dim) | source-weighted BPR (hs x2.0) |

Each condition trains fusion-5sig via source-grouped 5-fold CV
(val_fraction=0.25, 5 seeds = [20260725, 20260801, 20260802,
20260803, 20260804], PAIR_SEED=20260725).

Two fixed baselines always reported alongside:
- **rules**: tempo/key/tag_jaccard with weights [0.353, 0.235, 0.412]
- **cosine**: audio_cos_mean with weight 1.0

## Data

- LAION items: `research/data/fsld/items_laion-clap-music_packonly_train.jsonl`
  (1389 items, 484 sources, 512-dim)
- MS-CLAP items: `research/data/fsld/items_msclap_packonly_train.jsonl`
  (1389 items, 484 sources, 1024-dim)

## Hyperparameters (fixed, same as all prior runs)

- Adam, lr=0.05, 300 epochs
- val_fraction=0.25, 5 seeds
- Signals: audio_cos_mean, audio_cos_max, tempo, key, tag_jaccard

## Training modifications by condition

- **Uniform BPR** (conditions A, C): source_weights=None, neg_type_weights=None
- **Source-weighted BPR** (conditions B, D): source_weights=1/n_examples_per_source,
  neg_type_weights={"hard_similar": 2.0}

## Reporting

Per condition, report:
1. Val accuracy: overall, easy, hard_similar, hard_tempo_key (mean +/- std over 5 seeds)
2. Mean trained weights
3. Fusion-cosine delta on each regime

Main effects and interaction:
- Representation effect = mean(C,D) - mean(A,B)
- Training effect = mean(B,D) - mean(A,D)
- Interaction = D - C - B + A

All results reported regardless of outcome. Per-regime breakdowns mandatory.

## Scope

This is a **dev-set analysis** (5-fold CV on 484 train sources).
It does NOT touch the 121 held-out sources and provides no new
confirmatory evidence. Its purpose is mechanistic attribution of the
observed sensitivity, not a new significance claim.

## Known limitations

- Dev-set CV with the same hyperparameters and signal set used to
  develop the fusion; no hyperparameter search within this factorial.
- The factorial does not isolate embedding dimensionality (512 vs 1024)
  from embedding content.
- Source-weighted BPR and hard_similar upweighting are bundled as one
  "training recipe" factor; further disentangling would require a
  2x2x2 design.

## Errata (2026-11-16)

Found in an external review and recounted on the frozen inputs. No result
was re-run or changed; these correct how the results may be read.

1. **Training effect formula.** The line above reads
   `mean(B,D) - mean(A,D)`. The intended and computed main effect is
   `mean(B,D) - mean(A,C)` (`run_factorial.py`); the reported numbers use
   the correct formula.
2. **Not 5-fold CV.** The five seeds are five independent random
   source-level holdouts (val_fraction 0.25), not five mutually exclusive
   folds. Validation sources overlap across seeds.
3. **Validation is source-disjoint for queries, not for candidates.**
   Negatives are mined from the whole dev pool before the split, so
   training queries meet negatives from validation sources: at seed
   20260725, 383 of 680 training queries under LAION-CLAP and 393 of 680
   under MS-CLAP. The fusion never sees a source ID, but these dev numbers
   do not measure generalisation to unseen candidate sources. The
   held-out evaluation splits items before building pairs and is not
   affected.
4. **The representation factor also changes the test.** Each condition
   re-mines `hard_similar` in its own embedding space: of 981 queries
   present in both, 778 get a different `hard_similar` candidate under
   LAION-CLAP than under MS-CLAP. The "representation effect" therefore
   mixes the embedding change with a change of test negatives. Read it as
   the difference between two pipelines, not as the effect of the
   representation alone. Isolating it would need candidates frozen across
   conditions. The paper states this gap only as configuration
   sensitivity.
