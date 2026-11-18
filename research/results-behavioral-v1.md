# Behavioural Tests of Compatibility Scorers: Results (protocol v1)

Protocol: `research/protocol-behavioral-v1.md`, frozen at commit 460f7e9;
its dated erratum (2026-11-16) is appended at the end. The freeze is a local
Git commit, so it shows the order of work in this repository but cannot
prove that no exploratory runs happened before it.

Evaluation set: MUSDB18-HQ, 594 pairs from 149 tracks (6 of the 600
track-stem pairs had no window that met the rule). The reported features and
report were produced with the scoring code as frozen.

Report: `artifacts/compat-behavioral-musdb18/report.json`. Figures:
`artifacts/compat-behavioral-musdb18/figures/`.

A cell **passes** when its 95% interval lies above 0.5, is **inverted** when
it lies below, and is **inconclusive** otherwise (`blind` in the frozen JSON).
An inconclusive cell does not show that a scorer ignores the change; this is
not an equivalence test. Intervals are pointwise, with no correction for
multiple comparisons, so “Held” below means a cell met its prespecified
criterion, not that all hypotheses were confirmed together.

## Primary endpoints

Win rate of the reference over the altered copy, with the 95% interval.

| Scorer | P1 true vs random | P2 transposed (vs control) | P3 tape speed | P4 four beats late | P5 0.37 beat late |
|---|---|---|---|---|---|
| `clap_cos_mix` | 0.47 [0.44, 0.50] inverted | 0.39 [0.36, 0.42] inverted | 0.52 [0.49, 0.54] blind | 0.40 [0.36, 0.45] inverted | 0.47 [0.43, 0.51] blind |
| `clap_cos_mean` | 0.48 [0.45, 0.51] blind | 0.47 [0.44, 0.50] inverted | 0.54 [0.51, 0.56] passes | 0.44 [0.39, 0.49] inverted | 0.48 [0.44, 0.52] blind |
| `clap_cos_max` | 0.35 [0.33, 0.38] inverted | 0.47 [0.44, 0.49] inverted | 0.54 [0.51, 0.56] passes | 0.44 [0.39, 0.49] inverted | 0.47 [0.43, 0.51] blind |
| `laion_cos_mix` | 0.51 [0.48, 0.54] blind | 0.36 [0.34, 0.39] inverted | 0.52 [0.50, 0.55] blind | 0.51 [0.47, 0.56] blind | 0.49 [0.45, 0.53] blind |
| `fusion5_online` | 0.45 [0.42, 0.48] inverted | 0.46 [0.44, 0.49] inverted | 0.66 [0.64, 0.69] passes | 0.49 [0.44, 0.54] blind | 0.50 [0.46, 0.54] blind |
| `harmonic_transpose_invariant` | 0.48 [0.45, 0.50] blind | 0.49 [0.46, 0.52] blind | 0.52 [0.50, 0.54] passes | 0.44 [0.39, 0.49] inverted | 0.40 [0.36, 0.44] inverted |
| `tempo` | 0.62 [0.58, 0.65] passes | 0.50 [0.48, 0.51] blind | 0.66 [0.63, 0.68] passes | 0.53 [0.51, 0.55] passes | 0.52 [0.50, 0.53] passes |
| `key_exact` | 0.56 [0.54, 0.58] passes | 0.60 [0.58, 0.62] passes | 0.58 [0.56, 0.60] passes | 0.50 [0.48, 0.51] blind | 0.50 [0.50, 0.51] blind |
| `chroma_as_is` | 0.62 [0.60, 0.65] passes | 0.84 [0.81, 0.86] passes | 0.77 [0.75, 0.80] passes | 0.45 [0.39, 0.49] inverted | 0.43 [0.39, 0.48] inverted |
| `chroma_beat_aligned` | 0.64 [0.62, 0.66] passes | 0.84 [0.82, 0.87] passes | 0.80 [0.77, 0.82] passes | 0.74 [0.69, 0.78] passes | 0.53 [0.48, 0.57] blind |
| `rhythm_on_grid` | 0.66 [0.63, 0.69] passes | 0.33 [0.29, 0.36] inverted | 0.68 [0.65, 0.72] passes | 0.49 [0.43, 0.54] blind | 0.67 [0.63, 0.71] passes |
| `onset_pattern` | 0.89 [0.87, 0.91] passes | 0.35 [0.32, 0.38] inverted | 0.90 [0.87, 0.92] passes | 0.68 [0.63, 0.73] passes | 0.91 [0.88, 0.93] passes |
| `cocola` | 0.83 [0.81, 0.86] passes | 0.62 [0.59, 0.66] passes | 0.88 [0.86, 0.90] passes | 0.69 [0.64, 0.74] passes | 0.65 [0.61, 0.70] passes |

n: P1 4,752 comparisons, P2 445 pairs, P3 594, P4 402, P5 594. The rows for
`fusion5_with_key`, `key_fifth` and `progression_search` are in the report.

The rhythm scorers' inverted P2 cells are consistent with processing
confounding: the round-trip control went through the phase vocoder twice,
whereas the altered copy went through once. This unequal processing can
affect onsets; it does not uniquely separate pitch mismatch from artefacts.

## Predictions

| | Prediction | Outcome |
|---|---|---|
| H1 | Embedding-similarity scorers and `fusion5_online` pass none of P2, P4, P5 | **Held.** None passes; eight of the fifteen cells are inverted |
| H2 | `clap_cos_max` does not pass P1 | **Held.** 0.35, inverted. Shared room and production did not rescue it |
| H3 | `chroma_beat_aligned` passes P2, P3, P4; `chroma_as_is` passes P2, P3 and not P4; `rhythm_on_grid` and `onset_pattern` pass P3 and P5 | **Held** in all ten conditions (nine passes and one non-pass) |
| H4 | `harmonic_transpose_invariant` does not pass P2 | **Held.** 0.49, blind |
| H5 | For the two chroma scorers a semitone costs more than a fifth, and the octave is blind | **Held in part.** Semitone against fifth, in SD units: 0.62 against 0.23 (`chroma_as_is`), 0.61 against 0.37 (`chroma_beat_aligned`). The octave is blind for `chroma_beat_aligned` (0.51) but inverted for `chroma_as_is` (0.44 [0.40, 0.49]) |
| H6 | For `clap_cos_max` and `fusion5_online`, tempo changes win more often against the original than against the control | **Held.** 0.62 against 0.27, and 0.67 against 0.38 |
| H7 | `cocola` passes P1 to P5 | **Held** |

The secondary prediction failed: `laion_cos_mix` has an inconclusive win-rate result for a 6 dB
gain change here (0.52 [0.47, 0.56]), unlike on the development set.

## What the numbers say

1. **Similarity misses the mixed-role target relation.** In this P1 task,
   the CLAP cosine and deployed-fusion intervals do not support preferring
   the known same-recording target to a target from another song; MS-CLAP
   max pooling is inverted (0.35). In this mixed-role pool a high cosine does
   not pick out the true target. That does not mean similarity never matters
   for fit; it means it did not find this relation.
2. **Sensitivity depends on the processing comparison.** Against the
   original, embedding scorers prefer it to tempo-altered copies at rates
   of 0.55 to 0.67; using the round-trip reference reduces those rates to
   0.21 to 0.38. So part of what looked like tempo sensitivity is probably a
   reaction to the processing itself, although this cannot say how much: the
   control is processed twice and the altered copy once, so the two are not
   matched. With that control, `cocola`, `tempo` and `onset_pattern` give
   0.76, 0.62 and 0.89.
3. **Order of the harmony.** `chroma_as_is` and `chroma_beat_aligned` are
   level on transposition (0.84 each). With a four-beat delay, only the beat-aligned
   version passes (0.74 against 0.45). The fixed window gains earlier audio
   and loses its tail, so content, level and pitch-class profile need not
   stay identical. Meter and downbeats were not detected.
4. **Descriptive classical / coherence-model comparison.** Selecting a
   different training-free signal for each primary endpoint gives point
   estimates at or above `cocola`: P1 0.89
   (`onset_pattern`) against 0.83, P2 0.84 against 0.62, P3 0.90 against
   0.88, P4 0.74 against 0.69, P5 0.91 against 0.65. But no single classical
   signal passes all five, and `cocola` does. Picking the best signal for
   each endpoint flatters the classical side, so this does not show that any
   one classical method beats COCOLA; that would need paired differences
   between fixed methods. `COCOLA_HP_v1` was trained on MoisesDB, Slakh2100
   and CocoChorales (an earlier claim that it used MUSDB18-HQ is corrected in
   the protocol erratum), and its training files were not checked for
   overlap with this set.
5. **The deployed fusion** passes one endpoint, tape-speed change (0.66),
   and it does so through its tempo term.

## Findings outside the predictions

- **Gain.** `fusion5_online` shows directional level sensitivity: the copy 6 dB
  quieter outscores the original in 71% of pairs (0.29 [0.26, 0.32]).
  `clap_cos_mix` leans the other way (0.57 [0.53, 0.61]). `cocola` has a win rate
  near 0.50, but that alone does not mean it ignores level, since changes in
  opposite directions can cancel out. Showing that would take absolute score
  changes, ties and an equivalence margin fixed in advance.
- **Naming the change.** `progression_search` was meant to report the
  transposition or delay that would make a candidate fit. On real
  recordings it names the applied transposition in about half of the pairs
  (0.47 to 0.52) and a whole-beat delay in a third (0.32 to 0.40), and on
  untouched stems it reports "no transposition" only 51% of the time. On
  the development set these were 0.75 to 0.82 and 0.58 to 0.73. As it
  stands it is not reliable enough to show to a user.
- **`rhythm_on_grid`** is weaker on performed music (0.66 to 0.68) than on
  the quantised development set (0.85 to 0.90). `onset_pattern` is not.

## A bias to keep in mind

Scorers that cannot see alignment are not at 0.5 on the delay tests; several
sit at 0.40 to 0.45, preferring the delayed copy. The window rule picks the
earliest start at which the target is most active, so the audio just before
the window, which a delayed copy brings in, is on average slightly less
active. Together with the gain result this points to a possible level
effect. The direction and size of that bias for each scorer are unknown, so
it is not safe to say the P4 and P5 passes are understated. An inverted cell
reports the comparison as measured; it does not mean a scorer prefers music
that comes in late. Testing this properly would need a symmetric
advance-and-delay design with controls for content and window boundaries,
which v1 does not have.

## Limits

As in the protocol: same-recording stems are one known-good pairing among
possibly many; windows come from full songs; tempo, key and grid are
estimates; results describe scorers, not what musicians prefer.

The strongest signals here respond to particular edits and to timing. They
are not a general measure of compatibility, and nothing here asks musicians
what they prefer. Chroma and transposition matching are long-established;
what this work adds is the system, the evaluation design and the product
decisions drawn from where scorers failed.
