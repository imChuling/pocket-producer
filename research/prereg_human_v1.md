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

### 3.4 Rater

Single rater: the first author. No external participants are
recruited (project rule, 2026-10-29). The study is therefore a
pre-registered N-of-1 pilot and is labeled as such wherever it is
reported; it measures one trained listener's preferences against the
proxy, not population preference.

- 3 sessions, each covering all 40 pairs, at least 24 hours apart
- A/B side and pair order re-randomized per session (seed = session
  index); the rater does not see pair ids, ranker picks, or the
  previous sessions' answers
- The rater has seen `pairs.json` while building the study; to limit
  recall, pair ids are hidden at presentation time and sessions are
  spaced. This limitation is reported as-is.

### 3.5 Exclusion criteria

- A session with more than 90% identical choices (all A or all B) is
  discarded and re-run
- "No preference" responses are excluded from agreement calculation
  but reported as a separate statistic
- Pairs whose three session votes are not unanimous are kept, with
  the majority vote as the pair-level label and the disagreement
  reported as intra-rater inconsistency (§4.3.3)

## 4. Analysis plan

All code will be committed to `research/analyze_human_eval_v1.py`
before the first data collection session.

### 4.1 Primary analysis (H1)

Unit of analysis: the **pair**. The three sessions come from one
listener and are not independent, so they are collapsed to one label
per pair by majority vote (a pair with two or three "no preference"
votes is excluded from H1 and counted in §4.3). For each pair p:
- `agree_fusion(p)` = 1 if the majority vote matches fusion's pick
- `agree_cosine(p)` = 1 if it matches cosine's pick

    agreement_fusion = mean(agree_fusion over valid pairs)
    agreement_cosine = mean(agree_cosine over valid pairs)
    delta = agreement_fusion - agreement_cosine

Statistical test: on the pairs where fusion and cosine pick different
candidates (17 of 40 in `pairs.json`; on the other 23 both rankers
agree and the vote cannot separate them), count how many times the
majority vote sides with fusion and apply a two-sided exact binomial
test against 0.5. Report the count, the exact p-value, and a 95%
Clopper-Pearson interval on P(sides with fusion). The pooled delta
over all 40 pairs is reported descriptively with a pair-level
bootstrap CI (10,000 draws).

Decision rule: reject H0 at alpha = 0.05, which with 17 discordant
pairs requires at least 13 of 17 siding with fusion (exact two-sided
p = 0.049).

Power (exact binomial, n = 17; `research/power_sim_human_v1.py`,
`artifacts/human-eval-v1/power_sim.json`): majority voting over three
sessions sharpens a per-session preference (per-session 0.70 becomes
0.78 at the pair level). Power by per-session P(sides with fusion):
0.65 gives 0.45; 0.70 gives 0.70; 0.75 gives 0.89; 0.80 gives 0.97.
A single rater on 17 pairs can only detect a clear, consistent
preference (roughly 7 in 10 per session or stronger). This is the
accepted limitation of the N-of-1 design; the study is exploratory
and its contribution is the direction and size of the delta plus the
per-signal weight comparison (§4.3.2), not a significance claim.

Per-observation McNemar on (session, pair) observations is reported
as a secondary, descriptive statistic only, since sessions are not
independent.

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

3. **Intra-rater reliability:** fraction of pairs with unanimous
   votes across the three sessions, and Cohen's kappa between each
   pair of sessions. If mean kappa < 0.4, note that the rater's own
   judgments are unstable on this task and treat all other results as
   descriptive.

4. **Proxy label accuracy:** For each pair, the "proxy label" is
   the pack co-membership ground truth (positive = same pack).
   Report agreement between proxy labels and the rater's majority
   vote.

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

Each session's responses are stored as one file (`rater_id` is the
session label, e.g. `self_s1`):

```json
{
  "rater_id": "self_s1",
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
in that session, set by the randomization layer at presentation time.

Collected via `research/data/listening_test/rate.html`, a local static
page served from `research/data/` (for example `python3 -m http.server`),
which reads `pairs.json`, seeds order and A/B sides from the session
number (seed = 20261017 + 1000 x session), hides pair ids, and exports
`responses/<listener>_s<n>.json` (no login, no backend, no network).

## 7. Deviations log

Any deviation from this protocol after the freeze date will be
documented here with date, description, and justification.

- 2026-10-29 (before freeze, before any data): redesigned from a
  10 to 15 rater study to a single-rater, three-session N-of-1 pilot.
  Reason: project rule against evaluations involving other people.
  Analysis unit changed from (rater, pair) to pair (majority vote),
  primary test from McNemar to exact binomial; §3.4, §3.5, §4.1,
  §4.3.3, §6, §8 updated accordingly.

## 8. Timeline

- W1 (10/20): Build sampling script, download audio
- W2 (10/27): Build the local rating page; redesign to single rater
  (2026-10-29); freeze this document
- W3 (11/3): Three rating sessions, at least 24 h apart
- W4 (11/10): Analyze results
