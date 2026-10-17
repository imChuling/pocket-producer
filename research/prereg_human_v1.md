# Pre-registration: Human Preference vs Proxy Labels (v1)

Status: **DRAFT -- freeze before first data collection session.**
Date drafted: 2026-10-17
Author: Chuling Li

## 1. Research question

When deciding which audio loop to add next to a multi-loop session,
do human listeners agree more with the fusion ranker (5-signal
weighted combination) or with raw CLAP cosine similarity alone?

## 2. Hypotheses

- **H1 (primary):** The pairwise agreement rate between human
  preference and the fusion ranker is higher than between human
  preference and cosine-only, pooled across all 40 test pairs.

- **H2 (exploratory):** The fusion-vs-cosine agreement delta is
  larger on disagreement-stratum pairs (where the two rankers made
  opposite picks) than on hard_similar-stratum pairs (where they
  agreed). This tests whether fusion's advantage concentrates on
  the cases where it diverges from cosine.

H1 is confirmatory; H2 is exploratory and will be reported regardless
of direction.

## 3. Design

### 3.1 Stimuli

40 pairwise comparisons. Each trial presents:
- 2 to 4 **context loops** (the existing session), played sequentially
  or as a rough mix
- 2 **candidate loops** (A and B), randomized left/right per rater

Pair selection:
- **Stratum 1 (disagreement, ~17 pairs):** All hard_similar pairs
  where fusion and cosine make opposite picks (using the 5-seed mean
  fusion weights), sorted by |margin difference| descending, with
  source diversity preferred.
- **Stratum 2 (hard_similar, ~23 pairs):** Non-disagreement
  hard_similar pairs sorted by |margin difference| descending.
  Source diversity preferred (no two pairs from the same pack
  if possible).

Audio source: Freesound Loop Dataset (FSLD), previews downloaded
via `download_heldout_audio.py`. All items are from the pack-only
held-out split (121 sources, 408 items).

### 3.2 Task

For each pair, raters hear the context, then candidates A and B
(order randomized). They answer:

> "Which candidate fits better as the next loop in this session?"
> Options: A / B / No preference

Optional free-text: "Why?"

### 3.3 Randomization

- Candidate A/B assignment: randomized per rater per pair
  (fixed seed per rater ID)
- Pair presentation order: randomized per rater
- Answer codes map back to the ground-truth positive/negative
  identity only at analysis time

### 3.4 Participants

- Target: N = 10 to 15 raters with music production or active
  listening experience
- Recruitment: personal network, music technology communities
- No compensation (volunteer); estimated time ~20 minutes per rater
- If fewer than 10 raters are recruited by W3 end (2026-11-09),
  the study downgrades to a pre-registered N-of-1 pilot:
  the first author rates 120 pairs (3x the set, with repetitions
  for intra-rater reliability), and the report is labeled "pilot"

### 3.5 Exclusion criteria

- Raters who complete fewer than 30 of 40 pairs are excluded
- Raters with >90% identical responses (all A or all B) are excluded
- "No preference" responses are excluded from agreement calculation
  but reported as a separate statistic

## 4. Analysis plan

All code will be committed to `research/analyze_human_eval_v1.py`
before the first data collection session.

### 4.1 Primary analysis (H1)

For each rater r and each pair p, define:
- `agree_fusion(r, p)` = 1 if rater's choice matches fusion's pick,
  0 if it matches the other candidate, excluded if "no preference"
- `agree_cosine(r, p)` = 1 if rater's choice matches cosine's pick,
  0 otherwise

Metric: **pairwise agreement rate**, pooled across raters and pairs.

    agreement_fusion = mean(agree_fusion across all valid (r, p))
    agreement_cosine = mean(agree_cosine across all valid (r, p))
    delta = agreement_fusion - agreement_cosine

Statistical test: two-sided McNemar's test on the paired
(agree_fusion, agree_cosine) observations, treating each (rater, pair)
as one observation. Report p-value and 95% CI on the delta via
bootstrap (rater-clustered, 10,000 draws).

Decision rule: reject H0 (no difference) at alpha = 0.05.

Minimum detectable effect: McNemar's test is powered by the number
of discordant (rater, pair) observations (where the rater agrees with
one ranker but not the other). With N=10 raters x 40 pairs, the
upper bound is 400 observations, but the effective sample is limited
to the discordant subset. With 17 disagreement-stratum pairs and
an estimated 40-60% discordance rate across the full set, we expect
roughly 80-120 discordant observations, sufficient to detect a 15 pp
difference at 80% power (alpha=0.05). This is an exploratory study;
confidence intervals are the primary inferential tool.

### 4.2 Exploratory analysis (H2)

Repeat 4.1 separately for each stratum (disagreement, hard_similar).
Compare the fusion-vs-cosine delta between strata. Report per-stratum
deltas and CIs; do not apply a separate significance threshold
(this is exploratory).

### 4.3 Secondary analyses

1. **Three-ranker comparison:** Extend to rules-v1 baseline.
   Report agreement rates for all three rankers (rules, cosine,
   fusion) vs human.

2. **Weight comparison:** Run `finetune_from_feedback.py` with
   human labels as the target. Compare the resulting signal weights
   to the proxy-label weights:
   - Proxy weights (LAION-CLAP, 5 seeds): from
     `artifacts/heldout-eval-correction/sensitivity.json`
   - Human weights: from the finetune run
   Report per-signal weight differences and rank correlation.

3. **Inter-rater reliability:** Fleiss' kappa across all raters.
   If kappa < 0.4, note that the task may be too subjective for
   reliable pairwise evaluation.

4. **Proxy label accuracy:** For each pair, the "proxy label" is
   the pack co-membership ground truth (positive = same pack).
   Report agreement between proxy labels and human majority vote.

## 5. Pair sampling procedure

The exact 40 pairs will be determined by
`research/sample_listening_pairs.py` (to be committed before data
collection) with the following algorithm:

```
1. Build all hard_similar pairs from the held-out set using
   build_weak_pairs (seed=20260810)
2. Score every pair with three rankers using unified weights:
   - fusion: 5-seed mean weights [10.67, 5.35, 1.13, 0.006, 1.02]
   - cosine: audio_cos_mean signal only
   - rules: offline stand-in (tempo 0.30, key 0.20, tag 0.35, normalized)
3. Stratum 1 (disagreement): all hard_similar pairs where
   fusion_pick != cosine_pick, sorted by |margin diff| descending,
   source diversity preferred
4. Stratum 2 (hard_similar): remaining hard_similar pairs sorted
   by |margin diff| descending to fill up to 40 total,
   source diversity preferred
5. For each pair, record: source_id, positive/negative item_id,
   fusion_pick, cosine_pick, rules_pick, margins
```

## 6. Data format

Each rater's responses are stored as:

```json
{
  "rater_id": "anon_001",
  "timestamp": "2026-11-...",
  "responses": [
    {
      "pair_id": "d000",
      "choice": "A",
      "positive_side": "A",
      "reason": "...",
      "time_seconds": 45
    }
  ]
}
```

Fields: `choice` is "A", "B", or "no_preference". `positive_side`
records which side was assigned the positive (same-pack) candidate
for that rater, set by the randomization layer at presentation time.

Collected via static HTML form (no login, no backend).

## 7. Deviations log

Any deviation from this protocol after the freeze date will be
documented here with date, description, and justification.

## 8. Timeline

- W1 (10/20): Freeze this document, build sampling script, download audio
- W2 (10/27): Build listening test page, self-test
- W3 (11/3): Distribute to raters
- W4 (11/10): Analyze results
