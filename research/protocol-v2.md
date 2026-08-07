# Evaluation Protocol v2 — Preregistered Replication of the Signal–Human Dissociation

Status: FROZEN upon commit. Any change after the freeze commit requires a
new version file; results obtained under a modified protocol must be
labeled exploratory.

Motivation: the post-hoc exploratory analysis of 2026-08-07
(`artifacts/human-signal-alignment/alignment.json`) found that on
rater-consensus pairs, transpose-invariant harmonic compatibility matched
the human majority more often than CLAP cosine (7/9 vs 6/9), the sparse
role-gap signal was correct on all 3 pairs where it fired, and tempo —
the strongest theory signal on weak labels — fell below chance (3/9).
That analysis compared five signals on nine consensus pairs and proves
nothing. This protocol specifies the confirmatory study.

## H1 (primary, one-sided)

On rater-consensus pairs (majority ≥ 75% of raters), transpose-invariant
harmonic compatibility agrees with the human majority more often than
frozen CLAP cosine (mean-pooled, LAION-CLAP music, 512-dim).

## H2 (secondary, one-sided)

On the subset of pairs where the role-gap signal fires for exactly one
candidate, the fired candidate is the human majority choice more often
than chance (0.5).

## Signals (all five reported, no omissions)

1. `cos_mean` — cosine(mean context embedding, candidate)
2. `cos_max` — max over context items of cosine(item, candidate)
3. `harmonic` — transpose-invariant CQT chroma cross-correlation vs
   aggregated session chroma (`backend/ranking/harmonic_probe.py`)
4. `role_gap` — zero-shot role probe; candidate fills a role absent from
   context at confidence ≥ 0.18 (`backend/ranking/role_probe.py`)
5. `tempo` — tempo compatibility with half/double equivalence

Implementations are frozen at the commit that freezes this file. No new
signals may be added to the confirmatory analysis after data collection
begins.

## Sample size (power analysis)

Primary analysis is a paired comparison (McNemar, one-sided α = 0.05,
power 0.80). From the pilot: discordant rate (harmonic and cosine pick
different candidates) ≈ 8/19 ≈ 0.4; assumed true harmonic win rate among
discordant pairs 0.70 (pilot: 5/8).

Required discordant pairs:
n_d = (z₀.₀₅·0.5 + z₀.₂₀·√(0.7·0.3))² / (0.7 − 0.5)²
    = (1.645·0.5 + 0.842·0.458)² / 0.04 ≈ 37

Required consensus pairs: 37 / 0.4 ≈ 93. With the pilot's consensus
yield (10/20 = 50%), this needs ≈ 186 rated pairs. Target: **200 pairs,
≥ 9 raters per pair** (consensus = ≥ 75% of raters expressing a
preference).

For H2: role_gap fired on 3/19 pilot pairs (≈ 16%). To observe ≥ 30
fired pairs, the candidate pool is **stratified: at least 40% of pairs
constructed so the two candidates differ in predicted instrument role**
(one fills a context gap, one does not). Stratum membership is recorded
and reported.

## Pair construction

- Contexts: 2–4 fragments from a single source (session or pack).
- Candidates: one same-source held-out fragment, one cross-source
  fragment matched on duration; A/B position randomized per rater.
- Exclusions (decided before rating): fragments < 2 s, > 30 s, or with
  decode errors; raters completing < 80% of assigned pairs; attention-
  check failures (2 duplicated pairs per rater; both flipped answers →
  exclude rater).

## Analysis

- H1: McNemar exact test, one-sided, on consensus pairs; report all five
  signals' agreement with the majority, with 95% Wilson CIs.
- H2: exact binomial, one-sided, on fired-stratum consensus pairs.
- "Neither" votes count toward rater totals but pairs whose majority is
  "Neither" are excluded from H1/H2 and reported separately.
- No optional stopping: analysis runs once, after all ratings collected.

## Reporting

All five signals, both hypotheses, all exclusions, and the stratum
breakdown are reported regardless of outcome. Author ratings are
excluded. Raw per-rater labels ship in `artifacts/` with hashed rater
IDs.
