# Evaluation Protocol v3 — Frozen Held-Out Dual-Track Evaluation

Status: **FROZEN** upon commit `3726d0a9`. Any change after the freeze
commit requires a new version file (`protocol-heldout-v2.md`); results
obtained under a modified protocol must be labeled exploratory.

Frozen date: 2026-08-09

## Motivation

Protocol v2 specified a confirmatory replication (200 pairs, ≥9 raters,
McNemar on harmonic vs cosine). Two problems block it as written:

1. **No held-out data.** The existing 5-signal fusion and all baselines
   were trained/evaluated on the full 949-source FSLD corpus. The
   "294 unused packs" are quality-rejected (annotated=False in the FSLD
   manifest), not randomly held-out — they lack BPM/key/tag annotations
   required for signal computation.

2. **Two evaluation regimes measured different things.** The offline
   weak-label evaluation (949 sources, pack-membership pairs) and the
   human pilot (20 curated A/B pairs) used different corpora, different
   pair construction, and different sample sizes. The observed
   signal-ranking difference (tempo leads on weak labels, harmonic leads
   on human consensus) cannot be attributed to label semantics vs
   evaluation method.

This protocol fixes both by running **both evaluation tracks on the same
frozen held-out corpus**: a 20% source-stratified carve-out from the 949
usable FSLD sources.

## Design overview

```
949 usable FSLD sources
├── Train split (759 sources, ~2045 items)
│   └── Retrain 5-signal fusion (same hyperparams, same 5 seeds)
└── Held-out split (190 sources, ~513 items, 99 multi-item)
    ├── Track 1: Offline weak-label pairwise accuracy
    │   └── ~422 LOO examples, ~1266 pairs (3 negative types)
    └── Track 2: Human A/B on fusion–cosine disagreement pairs
        └── Mixed-effects model (method fixed + rater/pair random)
```

## Frozen artifacts

| Artifact | Value | Location |
|---|---|---|
| Base commit | `3726d0a95b70c8a1012fc6723a7311475ec15a86` | repo HEAD at freeze |
| Split seed | `20260809` | `artifacts/heldout-split/split.json` |
| Split fraction | 0.20 (190 of 949 sources) | same |
| Held-out ID SHA-256 | `82a6191c6e53b3c2...bb8beaed` | same |
| Embedding model | LAION-CLAP music, 512-dim | `items_laion-clap-music.jsonl` |
| Pair-construction seed | `20260725` (unchanged) | `run_fusion.py:PAIR_SEED` |
| Training seeds | `[20260725, 20260801, 20260802, 20260803, 20260804]` | `run_fusion.py:SEEDS` |
| BPR training | Adam, lr=0.05, 300 epochs, val_fraction=0.25 | `run_fusion.py:train_logistic` |
| Signals (5-signal fusion) | `audio_cos_mean, audio_cos_max, tempo, key, tag_jaccard` | `run_fusion.py:SIGNALS[:5]` |
| Cosine baseline | `cosine-mean-v1` (mean-pooled, no training) | `run_fusion.py` |

## Split construction

```python
import random
from collections import defaultdict

items_by_source = load_items_grouped_by_source("items_laion-clap-music.jsonl")
all_sources = sorted(items_by_source.keys())  # 949 sources
random.seed(20260809)
n_heldout = round(len(all_sources) * 0.20)    # 190
heldout = set(random.sample(all_sources, n_heldout))
train = set(all_sources) - heldout            # 759
```

The split is at the **source level** (pack or user), not the item level,
to prevent within-source leakage. Items from the same source never
appear in both train and held-out.

---

## Track 1: Offline weak-label evaluation

### Procedure

1. **Retrain** 5-signal logistic fusion on train-split sources only
   (759 sources), using the same 5 seeds, same BPR loss, same
   hyperparameters, same source-grouped internal val splits
   (val_fraction=0.25, grouped within train sources only).

2. **Construct LOO pairs** from held-out multi-item sources (99 sources,
   ~422 LOO examples). Same pair-construction code (`build_weak_pairs`
   with `PAIR_SEED=20260725`), same 3 negative types (easy,
   hard_tempo_key, hard_similar). Candidate pool for hard_similar
   negatives: **held-out items only** (no train-set items as negatives).

3. **Evaluate** pairwise accuracy of:
   - Frozen cosine baseline (cosine-mean-v1, no training)
   - 5-signal fusion (retrained on train split)
   - Each individual signal in isolation

4. **Report** mean ± std over 5 seeds, per negative type.

### Primary endpoint

**hard_similar pairwise accuracy**: fusion vs cosine-mean, mean over 5
seeds. This is the hardest negative type and the one where fusion showed
+4.0 pp on the full dataset.

### Secondary endpoints

- Overall pairwise accuracy (all negative types pooled)
- Per-negative-type accuracy (easy, hard_tempo_key, hard_similar)
- Per-signal LOSO contribution (leave-one-signal-out delta on hard_similar)

### Success criterion

Fusion hard_similar accuracy exceeds cosine-mean hard_similar accuracy
in ≥4 of 5 seeds. This is a descriptive criterion, not an inferential
test — the 5 seeds share the same held-out data and are not independent.

---

## Track 2: Human A/B evaluation on disagreement pairs

### Pair selection (disagreement algorithm)

From the ~422 held-out LOO examples, select pairs where fusion and
cosine **disagree on the hard_similar negative**:

```
For each LOO example e in held_out:
    positive = e.positive_item
    hard_neg = e.hard_similar_negative
    cosine_correct = cosine_score(positive) > cosine_score(hard_neg)
    fusion_correct = fusion_score(positive) > fusion_score(hard_neg)
    if cosine_correct != fusion_correct:
        disagreement_pairs.append(e)
```

These pairs are maximally informative: on every pair, exactly one method
is correct under the weak label. Human ratings reveal which method's
judgment aligns with perceived continuation utility.

**Target**: all available disagreement pairs (expected 30–80 based on
the full-dataset disagreement rate of ~10%). If fewer than 20
disagreement pairs exist, supplement with **concordant hard_similar
pairs** (both methods correct) up to 40 total, selected by smallest
margin (most uncertain), to provide a calibration baseline. Report the
two strata separately.

### Audio stimulus construction

For each pair, create two audio stimuli:

- **Context clip**: concatenate all items from the LOO source except the
  query, crossfaded (50 ms), loudness-normalized to −23 LUFS (EBU R128).
- **Candidate A / Candidate B**: the positive item and the hard_similar
  negative, randomly assigned to A/B positions. Each loudness-normalized
  to −23 LUFS independently. Randomization seed: `20260809 + pair_index`.

Deliver as: `[context 3s] [500ms silence] [candidate 3s]`, trimmed or
looped to exactly 3 seconds per segment. Export 44.1 kHz WAV.

### Raters

Target: **≥15 raters**, each rating all pairs. Raters must have ≥1 year
music production experience (self-reported). Recruitment: Prolific
(primary) + Audiotool community volunteers (capped at 30% of total
raters, flagged as source=volunteer).

### Rating task

Each trial: "Which candidate (A or B) would be more useful as the next
element in this musical context? Choose A, B, or Neither."

- **Neither** is an explicit third option, not a forced choice.
- Raters hear each pair once (no repeated measures per pair).
- 2 attention-check pairs per rater (exact duplicates with swapped A/B;
  both flipped → exclude rater).
- Rater order randomized; pairs presented in random order per rater.

### Exclusion rules (preregistered)

- **Raters**: exclude if <80% completion OR both attention checks failed.
- **Pairs**: none excluded based on agreement level. All pairs analyzed.
- **"Neither" votes**: included in the model as a third response category
  (see analysis below).

### Statistical analysis

#### Primary model: mixed-effects multinomial logistic regression

Response variable: rater choice ∈ {correct_method, incorrect_method, neither}
where "correct" and "incorrect" are defined by weak-label ground truth.

Fixed effects:
- `method_type`: which method agrees with the correct choice
  (fusion vs cosine) — the primary contrast

Random effects:
- `(1 | rater_id)`: rater intercept (accounts for rater-level bias)
- `(1 | pair_id)`: pair intercept (accounts for pair difficulty)

```r
library(lme4)
model <- glmer(
  choice ~ method_type + (1 | rater_id) + (1 | pair_id),
  family = binomial,  # correct vs incorrect, excluding Neither
  data = ratings_no_neither
)
```

The primary test: is the `method_type` coefficient significantly
different from zero? A positive coefficient for fusion means raters
agree with fusion's judgment more often than cosine's on disagreement
pairs.

#### Neither handling (preregistered)

Two analyses, both reported:

1. **Primary (exclude-Neither)**: Exclude Neither responses, fit
   binomial mixed-effects model on correct vs incorrect. This is the
   confirmatory test.

2. **Sensitivity (include-Neither)**: Fit multinomial with three
   response levels. Report whether the inclusion of Neither changes the
   direction or significance of the method_type effect. If primary and
   sensitivity disagree in direction, the result is NOT confirmed.

#### Secondary analyses

- **Per-signal alignment**: for each of the 5 signals, compute agreement
  with rater majority on consensus pairs (≥75% agreement). Report counts
  and 95% Wilson CIs. Descriptive only; no corrections.

- **Disagreement vs concordant strata**: if concordant pairs were
  included, report rater accuracy (agreement with weak label) separately
  for each stratum. Higher concordant accuracy validates the task design
  (raters can detect correct continuations when both methods agree).

- **Volunteer sensitivity**: if volunteer raters were used, refit the
  primary model on Prolific-only raters. If direction disagrees, primary
  result is NOT confirmed.

### Power simulation

Assumptions (from pilot data):
- 40 disagreement pairs, 15 raters → 600 observations
- True fusion advantage: 60% of raters pick fusion-correct candidate
  (vs 40% cosine-correct) on disagreement pairs
- ICC(rater) ≈ 0.05, ICC(pair) ≈ 0.10

```python
# Simplified power estimate (ignoring random effects, conservative)
from scipy.stats import norm
import numpy as np

n_pairs = 40
n_raters = 15
p_fusion = 0.60  # P(rater picks fusion-correct | disagreement pair)
p_null = 0.50
deff = 1 + (n_raters - 1) * 0.05  # design effect for rater clustering
n_eff = (n_pairs * n_raters) / deff
se = np.sqrt(p_fusion * (1 - p_fusion) / n_eff)
z = (p_fusion - p_null) / se
power = 1 - norm.cdf(norm.ppf(0.975) - z)
# Expected power ≈ 0.82 at alpha=0.05 two-sided
```

If fewer than 30 disagreement pairs are available, power drops below
0.70 and the study is reported as underpowered (descriptive only, no
inferential claim).

---

## Reporting

All results reported regardless of outcome:

1. Track 1 held-out accuracy table (per seed, per negative type)
2. Track 2 human ratings (all pairs, all raters passing exclusion)
3. Both Neither-handling analyses
4. Volunteer sensitivity analysis (if applicable)
5. Per-signal alignment on consensus pairs with Wilson CIs
6. All exclusions documented with counts and reasons

Raw per-rater labels shipped in `artifacts/heldout-human/` with hashed
rater IDs. Held-out split frozen in `artifacts/heldout-split/split.json`.

---

## Timeline

| Day | Task |
|---|---|
| 0 (freeze) | Commit protocol + split artifact |
| 1 | Embed held-out items, retrain fusion on train split |
| 1 | Run Track 1 offline evaluation |
| 2 | Select disagreement pairs, render audio stimuli |
| 2–3 | Deploy rating task (Prolific + volunteers) |
| 4–5 | Collect ratings, run exclusions |
| 6 | Analyze per protocol, update paper |
| 7 | Freeze final PDF |

## Amendments

### Amendment A1 (2026-08-09, before any data collection)

Independent −23 LUFS normalization of the two candidates interacts with
the 0.99 peak ceiling: on 19/90 rendered files the achievable loudness
fell below target, producing A/B loudness mismatches up to 3 dB within a
pair — a "louder wins" confound. Amended rule, applied before any rating
was collected:

- The two candidates in a pair are normalized to the **same** loudness:
  `min(−23 LUFS, max achievable for A, max achievable for B)` under the
  0.99 peak ceiling.
- The context clip keeps its own (possibly peak-limited) level; it is
  common to both stimuli in a pair and introduces no A/B asymmetry.
- Realized per-pair loudness is recorded in `answer_key.json`.

No other change. Any further change requires `protocol-heldout-v2.md`.
