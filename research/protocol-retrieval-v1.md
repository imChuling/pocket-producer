# Retrieval on the Behavioural-Test Store, Protocol v1

Status: **FROZEN at the commit that introduces this file.** No retrieval
figure had been computed on MUSDB18-HQ before that commit.

## Purpose

The behavioural tests (`protocol-behavioral-v1.md`) show which scorers can
tell a stem that fits from a damaged copy of it. They do not show how well
the classical signals do *together*, or how any scorer ranks the true stem
among real alternatives. This protocol measures that, on the features the
behavioural tests already stored. No audio is analysed again.

## What was already known

Stated because it limits how the results may be read.

- The behavioural report on these same recordings
  (`results-behavioral-v1.md`) was known when this was written.
- The combination `classic_grid` was written into the draft of this
  protocol before that report existed. `classic_onset`, the two
  `fusion_plus_classic` combinations as defined here, and the tempo-matched
  pool were added after it. Anything involving `onset_pattern` is therefore
  **post hoc** with respect to these recordings and is labelled so below.
- The MUSDB18-HQ store was read once before the freeze to count, per query,
  the tracks with a similar estimated tempo. Only tempo estimates were
  read; no scorer was run.

## Queries and pools

Code: `research/compat_tests/run_retrieval.py`.

A query is the context of a behavioural-test pair (594 on MUSDB18-HQ). Its
true target is ranked among targets from other tracks. Every candidate,
the true one included, has its beat-synchronous features pooled on the
query's grid from its stored frames.

| Pool | Candidates | Distractors drawn from |
|---|---|---|
| `any_role` | 50 | all targets of other tracks |
| `same_role` | 50 | targets of other tracks with the same stem type |
| `tempo_matched` | 10 | targets of other tracks whose grid tempo is within 2% of the query's |

Distractors are drawn with `numpy.random.default_rng([20261113, query
index, pool index])`. A query with fewer than 9 tempo-matched tracks is left
out of that pool. The tempo-matched pool reduces, and does not remove, the
advantage of signals that see tempo: 2% is still a drift of a fifth of a
second over the window.

## Scorers

All scorers of the behavioural protocol, and four combinations: sums of
scorers standardised (mean 0, SD 1) within the query's own pool. Nothing is
fitted and no weight is tuned.

| Name | Sum of | Status |
|---|---|---|
| `classic_grid` | `chroma_beat_aligned`, `rhythm_on_grid` | fixed before the behavioural report |
| `classic_onset` | `chroma_beat_aligned`, `onset_pattern` | post hoc |
| `fusion_plus_classic_grid` | `fusion5_online`, `chroma_beat_aligned`, `rhythm_on_grid` | fixed before the behavioural report |
| `fusion_plus_classic_onset` | `fusion5_online`, `chroma_beat_aligned`, `onset_pattern` | post hoc |

## Metrics

Rank of the true target, best is 1; tied candidates share the middle of the
ranks they span. Reported per scorer and pool: Recall@1, Recall@5,
Recall@10, mean reciprocal rank, and the median of (rank - 1) / (pool size -
1). Intervals: 95% percentile, 2,000 bootstrap resamples of whole tracks,
seed 20261113. Paired differences between two scorers are bootstrapped the
same way on per-query differences.

Chance Recall@1 is 0.02 in the two 50-candidate pools and 0.10 in the
tempo-matched pool.

## Primary endpoints

Recall@1 and mean reciprocal rank in the `same_role` pool, where timbre
cannot separate the target from the rest, for `fusion5_online`,
`classic_grid`, `classic_onset` and `cocola`, with these paired
differences:

- `classic_grid - fusion5_online`
- `classic_onset - fusion5_online` (post hoc)
- `fusion_plus_classic_grid - fusion5_online`
- `cocola - fusion5_online`
- `classic_grid - cocola` and `classic_onset - cocola`

Everything else is secondary: the other pools, the other scorers, and the
breakdown by stem type.

## Predictions

- **R1** `classic_grid` has higher Recall@1 than `fusion5_online` in the
  `same_role` pool (the interval of the difference lies above 0).
- **R2** Adding the classical signals to the deployed fusion raises its
  Recall@1 in the `same_role` pool (`fusion_plus_classic_grid -
  fusion5_online` above 0).
- **R3** `cocola` has higher Recall@1 than `fusion5_online` in the
  `same_role` pool.
- **R4** In the `any_role` pool the median normalised rank of
  `clap_cos_max` is above 0.5: the true stem ranks in the worse half.
- No prediction is made for the classical combinations against `cocola`, or
  for the tempo-matched pool. On the development set `classic_grid` was
  below `cocola` and `classic_onset` level with it.

## Reading the results

- Published stem-retrieval figures on MUSDB18 use whole-track embeddings
  and a pool of all 600 stems. These figures use 10 s windows and pools of
  50 or 10, and are not comparable with them.
- The true target is one stem known to fit. A distractor may fit too, so
  Recall@1 understates every scorer.
- Candidates are used as they are, at their own tempo and key. A producer
  can stretch and transpose a fragment; this protocol does not model that,
  and the tempo-matched pool only narrows the gap.
- COCOLA lists MUSDB18-HQ among its training sets.
- The development-set report (`artifacts/compat-retrieval-dev/`) has small
  and uneven pools (20 tracks) and is there to show the code runs.

## Runs

`run_retrieval` once on the MUSDB18-HQ store, output
`artifacts/compat-retrieval-musdb18/`. The code is not changed between the
freeze and that run; a forced change is recorded below with both sets of
numbers.

## Deviations

None.

### 2026-11-16 deviations and erratum (append-only)

The original v1 text above is retained. These corrections govern current
interpretation; no v1 query pool, scoring rule or result JSON is replaced.

1. **Stem candidates, not distinct songs.** The implementation counts and
   samples track-stem entries. The actual `tempo_matched` inclusion rule is
   at least nine eligible stems from other songs, not nine different songs.
   Of 545 included queries, 88 have fewer than nine eligible different songs;
   483 of the 545 sampled sets of nine distractors contain fewer than nine
   different songs. The 49 exclusions lack nine eligible stems. A rule that
   requires nine distinct songs would be a new v2 analysis. `same_role`'s
   main result is unaffected by this terminology correction. Counts are
   documented in `artifacts/compat-retrieval-musdb18/tempo-pools.json`.
2. **Chronology.** The original scorer table contradicts “What was already
   known”: `fusion_plus_classic_grid`, like the other fusion-plus-classic
   combination, was defined after the behavioural report and before the
   retrieval result. `classic_grid`'s earlier draft is an author account,
   not independently established by the first visible retrieval commit.
   The local Git sequence is behavioural freeze `460f7e9`, behavioural
   result `9af9906`, retrieval freeze `24d511e`, retrieval result `8c369c0`.
   This supports a local protocol-before-result record, not an external
   timestamp proving no prior computations. Retrieval hypotheses designed
   with behavioural knowledge of these recordings are not independent
   confirmation on unseen data, even when fixed before retrieval scoring.
3. **Checkpoint training data.** The actual `COCOLA_HP_v1` is listed as
   trained on MoisesDB, Slakh2100 and CocoChorales in the
   [official checkpoint table](https://github.com/gladia-research-group/cocola#pretrained-models).
   The prior MUSDB18-HQ assertion is unsupported for this checkpoint. See
   the behavioural protocol's dated erratum for the checkpoint hash and
   MIXED loader provenance. No independent reconstruction rules out overlap.
4. **Task boundary.** This is **as-is layering retrieval**: the true stem
   shares its context's song and time window, while other-song distractors
   keep their own tempo, phase, key and phrase. Pooling on a query grid does
   not align a distractor to it. Tempo matching reduces only one difference.
   These results do not demonstrate musician preference, or retrieval after
   time stretching / transposition / phase alignment. Other candidates may
   be musically useful; with no preference labels, the direction or magnitude
   of the resulting evaluation bias is unknown.
