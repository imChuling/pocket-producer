# MERT Sensitivity Extension Protocol v1

Status: **FROZEN at the commit that introduces this file.**

## Purpose

Third-representation extension of the configuration-sensitivity analysis:
does the fusion-vs-cosine conclusion move again under a non-CLAP audio
representation? Two representations (LAION-CLAP, MS-CLAP) showed a
7.8 pp swing; this run tests whether that is a two-model accident or a
pattern. Explicitly **not** confirmatory: the held-out split has been
evaluated twice before (LAION-CLAP, MS-CLAP). This is its third use and
must be labeled a sensitivity extension.

## Representation (pre-fixed)

- Model: **MERT-v1-95M** (audio-only self-supervised transformer).
  License verified before download and recorded in DATA_CREDITS.md.
- Input: audio resampled to the model's native 24 kHz, max 30 s
  (same clip policy as the CLAP embeddings).
- Pooling, locked before any run: unweighted mean over **all**
  transformer hidden layers, then mean over time. No layer selection,
  no learned pooling, no post-hoc tuning of either.
- Adapter: `backend/ranking/adapters/mert.py`, revision pinned to the
  checkpoint hash, model card recorded like the other adapters.

## Data

- Item selection: **identical items** to the existing pack-only corpus.
  `items_mert_packonly.jsonl` is built by embedding exactly the item
  ids present in `items_laion-clap-music_packonly.jsonl` (1,797 items,
  605 pack sources). No re-derivation of the selection.
- Split: `artifacts/heldout-split-packonly/split.json` (484 train /
  121 held-out, seed 20260810), unchanged.
- Pairs: `build_weak_pairs` with PAIR_SEED=20260725, unchanged.

## Baselines (fixed, always reported together)

Same three as protocol-msclap-sensitivity-v1: rules (no training),
cosine (audio_cos_mean, no training), fusion-5sig (source-weighted BPR,
hard_similar upweight 2.0). Signal set unchanged; only the audio
embedding space changes.

## Design

1. **Development (train side only).** `run_fusion.py` defaults:
   source-grouped CV, 5 seeds [20260725, 20260801-04]. Output
   `artifacts/fusion-mert/`.
2. **Held-out (single run).** Corrective protocol
   (protocol-heldout-correction-v1): retrain on the FULL 484-source
   train side per seed, evaluate once on the 121 held-out sources via
   `run_heldout_correction.py --mode mert`. **No re-runs permitted.**
   Output `artifacts/mert-sensitivity/` with provenance.json
   (artifact SHA, split SHA, n_bootstrap=10000, alpha=0.05,
   source-level resampling, seeds).
3. **Uncertainty.** Source-grouped bootstrap CIs, 10,000 draws,
   alpha=0.05, joint source resampling shared across seeds.
4. **LOSO replication** on held-out, as in the MS-CLAP run.

## Seed extension (pre-fixed)

To separate representation effects from seed noise, all three
representations are additionally run with 5 new seeds
[20260826, 20260827, 20260828, 20260829, 20260830], giving 10 seeds
per representation. Rules:

- The published 5-seed artifacts are never modified; 10-seed results go
  to `artifacts/fusion-{laion,msclap,mert}-seeds10/` and
  `artifacts/{heldout-eval,msclap-sensitivity,mert-sensitivity}-seeds10/`.
- The new seeds were chosen (dates) before any MERT number was seen.
- Reported quantity: per-representation fusion-vs-cosine hard_similar
  delta with per-seed spread; the cross-representation swing statistic
  is max minus min of the three deltas.

## Reporting

All results reported regardless of outcome, per-regime breakdowns
mandatory, three baselines side-by-side. The framing in any paper text
remains **configuration sensitivity**; no causal claims about why
representations differ.

## Known limitations

- Third evaluation of the same held-out split; independence is gone and
  every claim must carry the sensitivity-extension label.
- Signal set and hyperparameters were designed on the LAION-CLAP corpus.
- MERT is trained on music-only corpora with different objectives from
  the two CLAP models; representation differences confound model family,
  training data, and dimensionality. The analysis observes the swing,
  it does not attribute it.
