# Assignment on the Behavioural-Test Store, Protocol v1

Status: **FROZEN at the commit that introduces this file.** Written
2026-11-17. No assignment figure has been computed: the MUSDB18-HQ store is
on an external drive that was not connected when this was written, and the
analysis script was written after this file. After the run, this text
changes only through a dated, append-only "Deviations" section.

## Question

Grouping a new fragment into a project currently asks whether it *sounds
like* the project's fragments (MS-CLAP similarity). A project is made of
parts that *fit together*, such as a bass line and a drum loop from one
song, and those need not sound alike. This protocol asks: given one stem,
can a fit signal pick the context it came from among contexts from other
songs, where similarity cannot?

## What was already known

Stated because it limits how the results may be read.

- **This is not an independent validation.** It reuses the recordings and
  the stored features of the behavioural tests (`protocol-behavioral-v1.md`)
  and of retrieval (`protocol-retrieval-v1.md`), and both reports were
  known when this was written. On those recordings, retrieval found the
  classical beat signals well above the deployed fusion and MS-CLAP cosine
  when ranking stems for a context.
- The `onset_pattern` signal, and so `classic_onset` and
  `fusion_plus_classic_onset`, were chosen post hoc on these same
  recordings.
- What is new is the direction. Retrieval ranked candidate *stems* for one
  context. Assignment ranks candidate *contexts* ("projects") for one stem
  (the "fragment"). Retrieval did not measure this direction, and a scorer
  that ranks stems well for a context need not rank contexts well for a
  stem: the candidates differ in their own beat grids, mixes and number of
  parts.

## Data

The MUSDB18-HQ behavioural-test store (594 pairs from 149 tracks), read with
`run_behavioral.load_store`. Each pair is one track with one stem removed:
the removed stem is the query "fragment"; the remaining mix, with its own
beat grid and regions, is that pair's context. No audio is analysed again.

## Queries and pools

Code: `research/compat_tests/run_assignment.py`.

A query is one stem (594). It is scored against a pool of contexts: its own
context, plus contexts from other tracks. For every candidate context, the
query stem's beat-synchronous features are pooled from its stored frames on
**that context's** grid (`run_retrieval.on_query_grid` with the context as
the grid owner), as the stem would be heard placed into that project. No
transposition, time stretching or alignment search.

Pools are drawn by `run_retrieval.draw_pool`, unchanged, so each query's
candidate pair ids are exactly the ids retrieval drew for the same index and
pool; only the roles are swapped.

| Pool | Candidates | Other contexts drawn from | Status |
|---|---|---|---|
| `same_role` | 50 | contexts of other tracks whose removed stem has the query's type | primary |
| `any_role` | 50 | contexts of other tracks | secondary |
| `tempo_matched` | 10 | contexts of other tracks whose grid tempo is within 2% of the query track's | secondary |

In `same_role`, every candidate project is missing the same instrument as
the true one, so instrument composition cannot give the answer away. In
`any_role` it can. The tempo-matched pool keeps retrieval's rule: a query
with fewer than nine eligible contexts is left out of it (see retrieval's
dated deviation 1 for what "eligible" counts).

## Scorers

Every scorer `signals.score_all` returns for a (context, candidate) pair,
and retrieval's four combinations (`run_retrieval.COMBINATIONS`): sums of
scorers standardised (mean 0, SD 1) across the query's candidate contexts.
Nothing is fitted.

Named in the endpoints:

| Name | What it is |
|---|---|
| `fusion5_online` | the deployed fusion weights on MS-CLAP mean and max cosine to the context's regions, and tempo (no key, no tags) |
| `clap_cos_mean` | "plain cosine": MS-CLAP cosine between the stem and the mean of the context's region vectors, the closest analogue of comparing a fragment with a project's members |
| `classic_grid` | `chroma_beat_aligned` + `rhythm_on_grid` |
| `classic_onset` | `chroma_beat_aligned` + `onset_pattern` (post hoc) |
| `fusion_plus_classic_onset` | `fusion5_online` + `chroma_beat_aligned` + `onset_pattern` (post hoc) |
| `cocola` | only if its stored embeddings are present and the checkpoint loads on CPU; otherwise left out and the report says why |

`clap_cos_max` and `clap_cos_mix` are reported as secondary.

## Metrics

Rank of the true context among the pool (best 1; ties share the middle of
the ranks they span). Recall@1, Recall@5, Recall@10, mean reciprocal rank
and median normalised rank, with 95% percentile intervals from 2,000
bootstrap resamples of whole tracks, seed 20261113, using retrieval's
functions. Paired differences are bootstrapped the same way on per-query
differences. Chance Recall@1 is 0.02 in the 50-candidate pools and 0.10 in
the tempo-matched pool.

## Primary endpoints

Recall@1 and MRR in `same_role` for the six scorers above, and these paired
differences:

- each of `classic_grid`, `classic_onset`, `fusion_plus_classic_onset`,
  `cocola` minus `fusion5_online`;
- each of `classic_grid`, `classic_onset`, `fusion_plus_classic_onset`,
  `cocola` minus `clap_cos_mean`.

Everything else is secondary: the other pools, the other scorers, the
breakdown by stem type, and the nearest-neighbour analysis below.

## Secondary: stem-to-stem nearest neighbours (descriptive)

For each stem, its nearest neighbour among all other stems in the store:

- (a) by MS-CLAP cosine between the two stems' own vectors;
- (b) by `classic_onset` applied stem to stem: the first stem's stored
  features stand as the "context", the second stem's features are pooled on
  the first stem's track grid, and the sum of `chroma_beat_aligned` and
  `onset_pattern` is standardised across all other stems for that query.
  A stem with no beat grid, or with no pitched or onset content so that
  every candidate ties, is counted as "no neighbour".

Reported for each: the share of nearest neighbours that are the same stem
type from another song, another stem type from the same song, and another
type from another song. Two stems of one song share a grid exactly while
stems of other songs are pooled on a foreign grid, so (b) favours the same
song partly by construction. That is what fit is meant to see, and it is
also why (b) is descriptive only.

## Predictions

Written before any assignment score was computed.

- **A1** In `same_role`, `clap_cos_mean` and `fusion5_online` are weak:
  each has Recall@1 at most 0.10.
- **A2** `classic_onset` has higher Recall@1 than `fusion5_online` in
  `same_role` (interval of the paired difference above 0).
- **A3** `classic_onset` has higher Recall@1 than `clap_cos_mean` in
  `same_role` (interval above 0).
- **A4** `fusion_plus_classic_onset` has higher Recall@1 than
  `fusion5_online` in `same_role` (interval above 0).
- **A5** `classic_grid` has higher Recall@1 than `fusion5_online` in
  `same_role` (interval above 0).
- **A6** Under MS-CLAP cosine, more than half of nearest neighbours are the
  same stem type from another song, and fewer than a quarter are another
  stem type from the same song.
- **A7** Under `classic_onset`, more nearest neighbours are another stem
  type from the same song than the same type from another song.
- No prediction is made for `cocola`, for the `any_role` and
  `tempo_matched` pools, or for the breakdown by stem type.

## Reading the results

- The true context is one known good assignment, not the only acceptable
  one: a stem may also fit another project. Recall@1 understates every
  scorer, and by different amounts.
- MUSDB18-HQ stems are studio multitrack recordings with a steady beat, cut
  from the same song and time window as their context. Hummed ideas,
  free-tempo recordings and fragments without a beat are not represented,
  and the beat-synchronous fit signals do not apply to them.
- A "project" here is a three-stem context from one song. Product projects
  are collections of separately recorded fragments, at different tempos and
  keys, and are not modelled.
- These results do not show that musicians would group fragments this way.

## Runs

`run_assignment` once on the MUSDB18-HQ store, output
`artifacts/compat-assignment-musdb18/report.json`; results written to
`research/results-assignment-v1.md` with the outcome of each prediction,
including any that fail. The code is not changed between the freeze of the
script and that run; a forced change is recorded below with both sets of
numbers.

## Deviations

None.

### 2026-11-17 clarification of scope (append-only)

The text above is retained. This entry clarifies what the study measures;
it changes no query, pool, scorer, prediction or number.

The "Question" section frames the study as grouping fragments into
projects. The product does not group that way: it forms projects on
emotional and thematic kinship, as judged by the language model from tags,
text, and the creator's notes and edits, and this study does not address
that. What the study measures is whether a part fits a musical context
(tempo, harmony and rhythm lining up with the other parts), which is the
question the session rankers answer, `beat-fit-v1` among them. Its results
are filed with the fit and ranking evidence, not with grouping.
