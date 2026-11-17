# Assignment on the Behavioural-Test Store: Results (protocol v1)

Protocol: `research/protocol-assignment-v1.md`, frozen at commit 0f3da8c
before the script was written and before any score was computed. Script:
`research/compat_tests/run_assignment.py` (commit 3fb0282), run once on
2026-11-17 without changes. Report:
`artifacts/compat-assignment-musdb18/report.json`.

MUSDB18-HQ, 594 query stems from 149 tracks. Each stem is scored against a
pool of contexts (its own plus contexts from other tracks) and the task is
to rank its own context first. Intervals are 95% track-level bootstrap
intervals. This is not an independent validation: the recordings, the
stored features and the retrieval results on them were known beforehand,
and the onset combination was chosen post hoc on the same recordings.

## Primary endpoints: `same_role` pool

50 candidate contexts, all missing the same stem type as the query's own
context; chance Recall@1 is 0.02 and chance MRR 0.09.

| Scorer | Recall@1 | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|
| `clap_cos_mean` | 0.141 [0.111, 0.173] | 0.42 | 0.57 | 0.281 [0.251, 0.311] |
| `fusion5_online` | 0.207 [0.172, 0.246] | 0.47 | 0.61 | 0.338 [0.306, 0.373] |
| `classic_grid` | 0.301 [0.260, 0.341] | 0.47 | 0.57 | 0.401 [0.365, 0.435] |
| `classic_onset` (post hoc signal) | 0.540 [0.496, 0.584] | 0.76 | 0.84 | 0.646 [0.609, 0.684] |
| `fusion_plus_classic_onset` (post hoc signal) | 0.604 [0.559, 0.649] | 0.80 | 0.87 | 0.701 [0.663, 0.738] |
| `cocola` (no prediction) | 0.428 [0.381, 0.477] | 0.78 | 0.86 | 0.581 [0.543, 0.617] |

Paired differences in Recall@1:

| Difference | Value |
|---|---|
| `classic_onset - fusion5_online` | +0.333 [+0.280, +0.384] |
| `classic_onset - clap_cos_mean` | +0.399 [+0.346, +0.446] |
| `fusion_plus_classic_onset - fusion5_online` | +0.397 [+0.345, +0.447] |
| `fusion_plus_classic_onset - clap_cos_mean` | +0.463 [+0.413, +0.513] |
| `classic_grid - fusion5_online` | +0.094 [+0.042, +0.145] |
| `classic_grid - clap_cos_mean` | +0.160 [+0.113, +0.211] |
| `cocola - fusion5_online` | +0.221 [+0.158, +0.281] |

## Predictions

| | Prediction | Outcome |
|---|---|---|
| A1 | `clap_cos_mean` and `fusion5_online` each have Recall@1 at most 0.10 in `same_role` | **Not supported.** 0.141 and 0.207; both intervals lie above 0.10. Similarity is weak here but stronger than predicted |
| A2 | `classic_onset` above `fusion5_online` | **Supported.** +0.333 [+0.280, +0.384] |
| A3 | `classic_onset` above `clap_cos_mean` | **Supported.** +0.399 [+0.346, +0.446] |
| A4 | `fusion_plus_classic_onset` above `fusion5_online` | **Supported.** +0.397 [+0.345, +0.447] |
| A5 | `classic_grid` above `fusion5_online` | **Supported.** +0.094 [+0.042, +0.145] |
| A6 | Under MS-CLAP cosine, more than half of nearest neighbours are the same stem type from another song and fewer than a quarter another type from the same song | **Supported.** 586 of 594 (0.987) and 2 of 594 (0.003) |
| A7 | Under stem-to-stem `classic_onset`, other-type-same-song neighbours outnumber same-type-other-song | **Supported.** 198 (0.333) against 149 (0.251); the remaining 247 (0.416) are another type from another song |

Six of seven predictions held. A7 has no interval and is descriptive.

## Secondary pools (no predictions)

Recall@1, with chance in the header.

| Scorer | `any_role` (chance 0.02) | `tempo_matched` (chance 0.10) |
|---|---|---|
| `clap_cos_mean` | 0.017 [0.007, 0.030] | 0.090 [0.062, 0.121] |
| `fusion5_online` | 0.030 [0.017, 0.047] | 0.066 [0.043, 0.091] |
| `classic_grid` | 0.288 [0.248, 0.327] | 0.361 [0.328, 0.393] |
| `classic_onset` | 0.507 [0.461, 0.554] | 0.600 [0.559, 0.639] |
| `fusion_plus_classic_onset` | 0.404 [0.366, 0.442] | 0.444 [0.405, 0.481] |
| `cocola` | 0.473 [0.424, 0.520] | 0.543 [0.494, 0.591] |

In these two pools a candidate context may still contain the query's own
instrument. There the similarity scorers are at chance (`any_role`) or at
and below it (`tempo_matched`: the `fusion5_online` interval lies below
0.10). A likely reading is that a stem is most similar to mixes that already
contain its instrument, which are the wrong projects for it; this was not
tested directly. Adding the fusion score to the onset signal lowers
Recall@1 in both pools relative to `classic_onset` alone, the opposite of
what happens in `same_role`.

## By stem type (`same_role`, Recall@1, no predictions)

| Scorer | bass | drums | other | vocals |
|---|---|---|---|---|
| `clap_cos_mean` | 0.115 | 0.141 | 0.188 | 0.122 |
| `fusion5_online` | 0.182 | 0.215 | 0.262 | 0.169 |
| `classic_grid` | 0.460 | 0.195 | 0.423 | 0.128 |
| `classic_onset` | 0.710 | 0.503 | 0.698 | 0.250 |
| `fusion_plus_classic_onset` | 0.723 | 0.564 | 0.792 | 0.338 |
| `cocola` | 0.446 | 0.429 | 0.523 | 0.311 |

Every scorer is weakest on vocals.

## Reading

- For assigning a stem to its project, the beat-synchronous fit signals
  rank the true context first far more often than MS-CLAP similarity or the
  deployed fusion do. The direction matches retrieval on the same
  recordings and is measured here in the other direction, stem to project.
- MS-CLAP nearest neighbours are almost entirely the same instrument from a
  different song. A grouping rule built on that similarity groups by
  instrument type, not by song.
- The limits stated in the protocol apply: the true context is one good
  assignment among possibly several; the stems are studio multitrack with a
  steady beat cut from the same time window as their context; product
  projects made of separately recorded fragments at different tempos and
  keys are not modelled; nothing here shows how a musician would group.
- No multiple-comparison correction was applied across the seven
  predictions.
