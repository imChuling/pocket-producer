# Retrieval on the Behavioural-Test Store: Results (protocol v1)

Protocol: `research/protocol-retrieval-v1.md`, frozen at commit 24d511e.
MUSDB18-HQ, 594 queries from 149 tracks, run once with the code as frozen.
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

The tempo-matched pool has 545 queries; 49 had fewer than nine tracks
within 2% of their tempo.

By stem type in the `same_role` pool, vocals are the hardest target for
every scorer (`classic_onset` 0.26, `cocola` 0.19, `fusion5_online` 0.17)
and `other` the easiest (`fusion_plus_classic_onset` 0.79).
`chroma_beat_aligned` finds almost no drum target (0.01), as it should not.

## What the numbers say

1. **Similarity helps only once the stem type is fixed.** Among candidates
   of any type the embeddings and the deployed fusion are at or below
   chance (0.005 to 0.017 against 0.02): a different instrument from
   another song looks closer to the session than the missing one. Among
   candidates of the target's own type they are five to ten times chance
   (0.10 to 0.19). The earlier finding that similarity does not prefer the
   true stem is a statement about mixed-type candidates; within a type,
   similarity does carry information about the recording.
2. **The combination written down in advance did not beat the fusion** in
   the primary pool (R1). It did in the other two pools (+0.197 and
   +0.248). Added to the fusion it helped in all three.
3. **`onset_pattern` is the strongest single scorer** in every pool (0.52
   to 0.62), about twice `cocola` (0.25 to 0.31). It entered the
   combinations after the behavioural report on these recordings, so this
   is an observation to be confirmed on other data, not a tested claim.

## Limits

As in the protocol: 10 s windows and small pools, not comparable with
published whole-track figures; one known-good target per query, so Recall@1
understates every scorer; COCOLA lists MUSDB18-HQ among its training sets.

Candidates are scored as they are. A distractor keeps its own tempo and
starts wherever its window falls in the bar, while the true stem is in time
with its context, which favours the rhythm scorers and, to a lesser degree,
`cocola`. Scoring candidates after mapping them onto the query's grid is
possible from the stored features and is left for later work.
