# Behavioural Tests of Compatibility Scorers, Protocol v1

Status: **FROZEN at the commit that introduces this file.** MUSDB18-HQ was not
scored before that commit.

## Purpose

The ranking work so far is evaluated against proxy labels (pack
co-membership), and the paper's own finding is that conclusions move with the
label definition. This study asks a question that needs no label: given a
stem that is known to fit its context, and a copy of it changed in a way
that must fit worse, does a scorer prefer the original?

It also tests whether a classical, beat-synchronous signal passes the tests
that pooled embeddings fail.

Every result is reported, whatever its direction.

## Data

- **Development: BabySlakh** (Zenodo 4603870, 20 tracks, 16 kHz, MIDI
  renders, CC BY 4.0). Used to build and debug the method. Its numbers in
  `artifacts/compat-behavioral-dev/` are descriptive only and are the source
  of the predictions below.
- **Evaluation: MUSDB18-HQ** (Zenodo 3338373, `musdb18hq.zip`, md5
  `12d4f2ecd55245a4688754dd76363103`, 150 tracks, four stems each). Both
  folders are used: nothing in this study is fitted, so there is no train
  side. Before the freeze the archive was checksummed, listed, and read for
  two tracks to check the reader's shapes and sample rate. No scorer was run
  on it.

## Pairs

One pair per (track, stem): the stem is the target, the other stems are the
context. Code: `research/compat_tests/datasets.py`, `musdb.py`.

- Window: 10 s, starting on a whole second, chosen as the start that
  maximises the share of seconds where the target sounds (RMS above -50
  dBFS) plus the share of other stems that sound in at least 80% of the
  window. A pair is dropped when no window has the target sounding in 80% of
  its seconds with at least two other stems playing.
- The target is stored with 4.5 s before and 1.5 s after the window so that
  delays and stretches read real audio.
- Context mix: the sum of the other stems in the window. Session regions:
  the other stems separately (the four loudest), as the product sees a
  session.
- Beat grid: constant tempo, estimated from the context mix
  (`beatgrid.grid_from_frames`). Candidates are analysed on the context's
  grid, never their own.

## Scorers

All in `research/compat_tests/signals.py`. Product code is called directly
where it exists.

| Name | Definition |
|---|---|
| `clap_cos_mix` | MS-CLAP cosine, context mix to candidate |
| `clap_cos_mean`, `clap_cos_max` | MS-CLAP cosine to session regions, mean- and max-pooled (the deployed cosine terms) |
| `laion_cos_mix` | LAION-CLAP (music checkpoint) cosine, context mix to candidate |
| `cocola` | COCOLA_HP_v1 pairwise score, context mix to candidate, first 5 s |
| `tempo` | `tempo_match` on tempos estimated as at ingest |
| `key_exact`, `key_fifth` | `key_match` on keys estimated as at ingest |
| `harmonic_transpose_invariant` | the deployed chroma probe score, best of 12 transpositions |
| `chroma_as_is` | cosine of mean chroma without transposition |
| `fusion5_online` | deployed fusion weights on (cos mean, cos max, tempo, key = 0, tags = 0), before the sigmoid |
| `fusion5_with_key` | the same with the estimated key |
| `chroma_beat_aligned` | mean per-beat chroma cosine on the context grid |
| `progression_search` | best per-beat fit over 12 transpositions and delays of up to 4 beats |
| `rhythm_on_grid` | share of the candidate's onset energy on sixteenth-note positions of the context grid |
| `onset_pattern` | correlation of context and candidate onset patterns on the grid |

MS-CLAP hears the first 7 s of a window, LAION-CLAP the first 10 s, COCOLA
the first 5 s. COCOLA's training data includes MUSDB18-HQ, so its numbers
here are in-domain and are not a like-for-like baseline.

## Tests

Code: `research/compat_tests/perturb.py`. Each perturbation is applied to
the target only.

| Family | Values | Kind | Applies to |
|---|---|---|---|
| pitch | -6, -3, -2, -1, +1, +2, +3, +6 semitones | directional | pitched stems |
| pitch | +7, +12 semitones | exploratory | pitched stems |
| tempo | -12, -6, -3, +3, +6, +12 percent | directional | all |
| varispeed (resampling: pitch and tempo together) | -2, -1, +1, +2 semitones | directional | all |
| beatshift (pure delay, in beats of the context) | 0.37, 0.5, 1, 2, 4 | directional | all, when the delay fits in the lead-in |
| gain -6 dB, polarity | | invariance | all |
| pitch round trip (+1 then -1), tempo round trip (x1.06 then back) | | control | as their family |

Pitch and tempo use a phase vocoder. Their round-trip controls went through
the same processing twice and ended where they started. Varispeed and
beatshift involve no time-frequency processing.

Drums are treated as unpitched: bass, other and vocals take the pitch tests.

## Statistic

For a scorer and a test, each pair gives a win (1), tie (0.5) or loss (0)
for the reference over the perturbed copy. The reference is the original,
and for the pitch and tempo families also the round-trip control. Reported:
mean win rate, 95% percentile interval from 2,000 bootstrap resamples of
whole tracks (seed 20261112), tie rate, and the mean score drop in units of
the scorer's standard deviation over random candidates.

Random candidates: for each pair, 8 targets from other tracks, drawn with
`numpy.random.default_rng([20261112, pair index])`, analysed on that pair's
grid.

A cell is read as **passes** when the interval lies above 0.5, **inverted**
when it lies below, and **blind** otherwise.

## Primary endpoints

Fixed before scoring. One figure per scorer for each:

- **P1** true target against random targets.
- **P2** pitch, pooled over the eight directional shifts, against the
  round-trip control (each pair contributes its mean win).
- **P3** varispeed, pooled over the four shifts, against the original.
- **P4** one-bar delay (`beatshift4`) on pitched targets whose harmony moves:
  the target's own beat chroma differs from its delayed self by at least
  0.05 (`MIN_HARMONIC_CHANGE`), a rule that looks only at the target.
- **P5** off-grid delay (`beatshift0.37`), all targets.

Everything else is secondary: single tests, the tempo family against its
control, per-role subsets, invariance tests, and whether
`progression_search` names the transposition or delay that was applied.

## Predictions

From the development set. They are stated so that the evaluation can
contradict them.

- **H1** The embedding-similarity scorers (`clap_cos_mix`, `clap_cos_mean`,
  `clap_cos_max`, `laion_cos_mix`) and `fusion5_online` pass none of P2, P4
  and P5.
- **H2** `clap_cos_max` does not pass P1. On real recordings shared room and
  production may help it, so this is the prediction most likely to fail.
- **H3** `chroma_beat_aligned` passes P2, P3 and P4. `chroma_as_is` passes
  P2 and P3 and does not pass P4. `rhythm_on_grid` and `onset_pattern` pass
  P3 and P5.
- **H4** `harmonic_transpose_invariant` does not pass P2, by construction.
- **H5** For `chroma_as_is` and `chroma_beat_aligned` the mean drop is
  larger for a semitone (mean of -1 and +1) than for a fifth (+7), and the
  octave (+12) is blind.
- **H6** For `clap_cos_max` and `fusion5_online` the pooled tempo win rate
  against the original is higher than against the control: part of their
  apparent sensitivity is processing artefacts.
- **H7** `cocola` passes P1 to P5. It is the one scorer here trained for
  coherence between stems, and both datasets are close to its training data
  (BabySlakh is a subset of Slakh2100; MUSDB18-HQ is listed among its
  training sets), so this is a statement about an in-domain model.

Secondary, also from the development set: `laion_cos_mix` is not invariant
to a 6 dB gain change (the original won 0.88 of the time where 0.5 is
expected).

## Runs

`features` once per pair (resumable; a crash is resumed, not restarted with
changes), then `report` once. Output: `artifacts/compat-behavioral-musdb18/`.
The scoring code is not changed between the freeze and the report. If a
defect forces a change, it is recorded below with the commit and both sets
of numbers are kept.

## Limits

- Same-recording stems are one known-good pairing, not the only one; a
  random target may also fit. P1 is therefore a lower bound on a scorer's
  ability, and the directional tests do not depend on it.
- The windows come from full songs, not from short loops as in the product.
- Tempo, key and the beat grid are estimated and carry their own errors.
- A whole-beat delay is harmless where the harmony repeats; P4 is restricted
  for that reason, and the restriction rule is fixed above.
- Results speak about scorers, not about what musicians prefer.
- BabySlakh is 16 kHz synthesised audio and the embedding models were
  trained on full-band recordings, so the development numbers may understate
  them; that is one reason the predictions are tested on real recordings.

## Deviations

None.
