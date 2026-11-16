# Retrieval on the Behavioural-Test Store: Results (protocol v1)

Protocol: `research/protocol-retrieval-v1.md`, frozen at commit 24d511e.
The 2026-11-16 append-only protocol deviations correct pool terminology,
combination chronology and checkpoint provenance. The Git sequence records
a local freeze before results, not independently timestamped preregistration.
MUSDB18-HQ, 594 queries from 149 tracks in the recorded formal run with
the scoring code as frozen.
Report: `artifacts/compat-retrieval-musdb18/report.json`.

## Primary endpoints: `same_role` pool

50 candidates of the target's own stem type; chance Recall@1 is 0.02 and
chance MRR 0.09.

| Scorer | Recall@1 | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|
| `fusion5_online` | 0.194 [0.156, 0.234] | 0.43 | 0.57 | 0.320 [0.286, 0.359] |
| `classic_grid` | 0.237 [0.203, 0.277] | 0.43 | 0.53 | 0.344 [0.310, 0.378] |
| `classic_onset` (post hoc) | 0.527 [0.483, 0.568] | 0.75 | 0.82 | 0.636 [0.598, 0.672] |
| `fusion_plus_classic_grid` | 0.310 [0.268, 0.352] | 0.55 | 0.67 | 0.431 [0.394, 0.469] |
| `fusion_plus_classic_onset` (post hoc) | 0.581 [0.534, 0.627] | 0.79 | 0.86 | 0.679 [0.641, 0.716] |
| `cocola` | 0.273 [0.232, 0.315] | 0.57 | 0.69 | 0.415 [0.375, 0.455] |

Paired differences in Recall@1:

| Difference | Value |
|---|---|
| `classic_grid - fusion5_online` | +0.044 [-0.003, +0.088] |
| `classic_onset - fusion5_online` (post hoc) | +0.333 [+0.273, +0.393] |
| `fusion_plus_classic_grid - fusion5_online` | +0.116 [+0.074, +0.162] |
| `cocola - fusion5_online` | +0.079 [+0.024, +0.136] |
| `classic_grid - cocola` | -0.035 [-0.086, +0.012] |
| `classic_onset - cocola` (post hoc) | +0.254 [+0.197, +0.310] |

## Predictions

| | Prediction | Outcome |
|---|---|---|
| R1 | `classic_grid` above `fusion5_online` on Recall@1, same role | **Not supported.** +0.044, and the interval reaches zero |
| R2 | Adding the classical signals raises the deployed fusion's Recall@1 | **Held.** +0.116 [+0.074, +0.162] |
| R3 | `cocola` above `fusion5_online` | **Held.** +0.079 [+0.024, +0.136] |
| R4 | `clap_cos_max` ranks the true stem in the worse half, any role | **Held.** Median normalised rank 0.66 [0.64, 0.69] |

## Other pools

Recall@1, with chance in the header.

| Scorer | `any_role` (0.02) | `same_role` (0.02) | `tempo_matched` (0.10) |
|---|---|---|---|
| `clap_cos_max` | 0.005 | 0.115 | 0.017 |
| `laion_cos_mix` | 0.010 | 0.104 | 0.086 |
| `fusion5_online` | 0.017 | 0.194 | 0.042 |
| `chroma_as_is` | 0.057 | 0.079 | 0.193 |
| `chroma_beat_aligned` | 0.072 | 0.111 | 0.171 |
| `rhythm_on_grid` | 0.194 | 0.189 | 0.255 |
| `onset_pattern` | 0.520 | 0.532 | 0.617 |
| `classic_grid` | 0.214 | 0.237 | 0.290 |
| `classic_onset` | 0.503 | 0.527 | 0.571 |
| `cocola` | 0.254 | 0.273 | 0.312 |

The tempo-matched pool has 545 queries; 49 had fewer than nine eligible
**stems** from other songs within 2% of their tempo. The frozen protocol
said tracks, but implementation counts stem candidates. Among included
queries, 88 have fewer than nine eligible different songs; 483/545 actual
pools draw their nine distractors from fewer than nine different songs.
This deviation does not change the `same_role` primary pool or v1 JSON.

By stem type in the `same_role` pool, vocals are the hardest of the four
roles for `classic_onset` (0.26), `cocola` (0.19) and `fusion5_online`
(0.17). These role orderings are not universal: chroma scorers do worse on
drums. `other` reaches 0.79 for `fusion_plus_classic_onset`, but is not
every scorer's easiest role.
`chroma_beat_aligned` finds almost no drum target (0.01).

## What the numbers say

1. **Similarity is more useful here within a stem type.** Among candidates
   of any type the embedding/fusion Recall@1 point estimates range from
   0.005 to 0.024 against chance 0.02; `clap_cos_mean` is 0.0236, so they
   are not all at or below chance. These point estimates alone do not
   establish a significant chance comparison. In these mixed-role pools,
   other-song instruments frequently rank above the true target. Among
   candidates of the target's own type they are five to ten times chance
   (0.10 to 0.19). The earlier finding that similarity does not prefer the
   true stem is a statement about mixed-type candidates; within a type,
   similarity does carry information about the recording.
2. **`classic_grid` did not show a clear advantage over fusion** in
   the primary pool (R1). It did in the other two pools (+0.197 and
   +0.248). Added to the fusion it helped in all three. The fusion-plus-
   classical combinations were defined after the behavioural report and
   before retrieval scoring; the original protocol table conflicts on that
   chronology. They are not independent confirmation on unseen recordings.
3. **`onset_pattern` is the strongest single scorer** in every pool (0.52
   to 0.62), about twice `cocola` (0.25 to 0.31). It entered the
   combinations after the behavioural report on these recordings, so this
   is an observation to be confirmed on other data, not a tested claim.

The two-signal `classic_onset` combination has not shown incremental
retrieval benefit over `onset_pattern` alone. Recall@1 is 0.5034 versus
0.5202 (`any_role`), 0.5269 versus 0.5320 (`same_role`) and 0.5706 versus
0.6165 (`tempo_matched`). No paired interval was computed for this contrast,
so these are descriptive point estimates, not a significant disadvantage.
Using chroma plus onset in the local product is a design choice to consider
harmony as well as rhythm, with its incremental value still unvalidated.

## Limits

As in the protocol: 10 s windows and small pools, not comparable with
published whole-track figures; one known-good target per query, with other candidates potentially useful
but not preference-labelled. This prevents a direct translation of Recall@1
into musical utility; it does not establish a universally conservative bias.
The actual `COCOLA_HP_v1` lists MoisesDB, Slakh2100 and CocoChorales, not
MUSDB18-HQ, as its training sets (see protocol erratum); actual training-file
overlap was not independently reconstructed.

Candidates are scored as they are. A distractor keeps its own tempo and
starts wherever its window falls in the bar, while the true stem is in time
with its context, which favours the rhythm scorers and, to a lesser degree,
`cocola`. Pooling their features on the query grid is already done; it does not
perform tempo, phase, key or phrase alignment. Symmetric adaptation of all
candidates, and evaluation on independent recordings, remain future work.
These **as-is layering retrieval** results do not establish listener
preference or usefulness after stretching/transposition. Intervals are
pointwise without multiple-comparison control; “Held” describes each
listed criterion under that limitation.
