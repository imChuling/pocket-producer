# Protocol: Held-Out Correction v1

**Status:** post-hoc protocol correction (NOT confirmatory)
**Date:** 2026-08-13
**Motivation:** protocol-msclap-sensitivity-v1 (line 52) specifies
"Retrain fusion on full train side" but both `run_heldout_eval.py` and
`run_msclap_sensitivity.py` used `val_fraction=0.25`, training each seed
on ~75% of the 484 train sources. The internal validation subset was not
used for early stopping or model selection; its only effect was reducing
training data. This correction re-runs held-out evaluation with each seed
trained on ALL 484 train sources, as originally specified.

## Scope

- LAION-CLAP held-out evaluation (correcting `run_heldout_eval.py`)
- MS-CLAP held-out evaluation (correcting `run_msclap_sensitivity.py`)
- Same 121-source held-out split (seed 20260810, `split.json` unchanged)
- Same hyperparameters, seeds, negative regimes, bootstrap method

## Design

1. **Training.** For each of the 5 seeds, train logistic fusion on the
   FULL set of train examples from 484 train sources. No internal
   validation split. Fixed 300 epochs (no early stopping).

2. **Evaluation.** Evaluate on the 121-source held-out split. Three
   baselines: rules (hand-tuned), cosine (frozen), fusion (5-signal).

3. **LAION-CLAP.** Standard BPR (no source weighting, no neg-type
   upweight) to match the original LAION-CLAP recipe.

4. **MS-CLAP.** Source-weighted BPR with hard_similar x2.0, matching
   `protocol-msclap-sensitivity-v1`.

5. **Bootstrap CIs.** Source-grouped, 10,000 draws, alpha=0.05, joint
   source resampling shared across seeds.

6. **LOSO.** Leave-one-signal-out on held-out (MS-CLAP only).

## Artifacts

- `artifacts/heldout-eval-correction/` (LAION-CLAP, full-train)
- `artifacts/msclap-sensitivity-correction/` (MS-CLAP, full-train)
- Old artifacts preserved unchanged in `artifacts/heldout-eval-packonly/`
  and `artifacts/msclap-sensitivity/`

## Reporting

All results reported regardless of outcome. If numbers change
materially, update lbd.tex Table 1 and prose. If not, note convergence
in ledger and keep original numbers (which used more conservative
training on fewer examples).

## No re-runs

Each configuration runs exactly once. No re-runs permitted after seeing
results.
