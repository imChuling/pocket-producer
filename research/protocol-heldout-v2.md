# Held-Out Evaluation Protocol v2 — Pack-Only Corpus

Status: **FROZEN at the commit that introduces this file.** The freeze is
provable by construction: this protocol and the split artifact are
committed together, before any evaluation run touches the held-out side.
Any later change to this file or to `artifacts/heldout-split-packonly/`
invalidates the confirmatory claim.

## Why v2 exists

Two defects in the v1 evaluation (`protocol-heldout-v1.md`) require a
full re-run:

1. **The v1 freeze was not real.** The protocol file referenced base
   commit `3726d0a9`, which predates the file and does not contain it;
   the protocol's mtime postdates `eval.json`. v1 results are therefore
   demoted to exploratory and the preregistration claim was retracted
   (see ledger P1).
2. **~26% of v1 examples were not pack co-membership.** The manifest
   falls back to `user:<username>` as source_id when a sound has no
   pack. Same-uploader grouping is a weaker proxy for shared production
   context. v2 drops every `user:`-grouped source.

## Corpus

- Items: `research/data/fsld/items_laion-clap-music.jsonl` filtered by
  `research/filter_pack_only.py` (drops `user:` sources) →
  `items_laion-clap-music_packonly.jsonl`
- 1,797 items, 605 pack sources (338 packs have ≥2 items and yield
  queries)
- Weak labels: pack co-membership only — every positive shares a
  Freesound pack with its query

## Split (frozen)

- Generator: `research/make_heldout_split.py`, seed **20260810**,
  fraction 0.2
- 605 sources → **484 train / 121 held-out**
- Artifact: `artifacts/heldout-split-packonly/split.json`
- SHA-256 of held-out id list:
  `3f4967ca916ac5a985388836f9fb60e44bef93c3f73d2df7ee1c37ee4f36384c`

## Design

1. **Development (train side only).** Fusion training, signal-set
   choices, and LOSO ablation run exclusively on the 484 train sources
   (`filter_pack_only.py --train-only` produces the train items file).
   Internal validation uses the existing 5-seed source-grouped CV in
   `run_fusion.py` / `run_ablation.py`.
2. **Confirmatory (held-out side, single run).** `run_heldout_eval.py`
   retrains fusion on the train side (5 seeds, same hyperparameters:
   BPR, Adam, 300 epochs, lr 0.05) and evaluates once on the 121
   held-out sources. **No re-runs permitted.** Whatever comes out gets
   reported.
3. **Uncertainty.** `bootstrap_heldout.py` computes source-grouped
   bootstrap CIs (10,000 draws, α=0.05). Pooled CI uses **joint source
   resampling shared across all 5 seeds** — the seeds share one test
   set, so a single source draw is applied to every seed within each
   bootstrap iteration (the v1 positional averaging of independent
   per-seed draws was invalid and is fixed in the same commit as this
   protocol).
4. **LOSO replication.** `loso_heldout.py` repeats the
   leave-one-signal-out ablation with train-side retraining and
   held-out evaluation, to test whether regime-dependent signal
   contributions replicate.

## Pre-registered wording tiers (bootstrap CI on hard_similar delta)

| CI outcome | Manuscript wording |
|---|---|
| entirely > 0 | "small but positive held-out gain" |
| crosses 0 | "the held-out difference was small and uncertain" |
| entirely < 0 | "did not replicate" |

## Known residual limitations (stated in advance)

- The pack-only corpus is a **subset of data already inspected** during
  v1 and earlier development. The signal set and hyperparameters were
  designed on the full (pack+user) corpus. This run is a sensitivity
  re-analysis under a cleaner labeling assumption, not de novo
  confirmatory evidence; the paper must not claim otherwise.
- Held-out negatives are mined within the held-out pool (513→smaller
  pack-only pool). Absolute accuracies are not comparable between train
  and held-out pools; only the within-pool fusion−cosine delta is
  interpretable.
- `easy` / `hard_tempo_key` negative regimes are constructed from
  tempo/key; tempo's LOSO contribution to those regimes is partly
  built in by construction, and the paper must say so.
