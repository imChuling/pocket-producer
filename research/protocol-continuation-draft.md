# Continuation Tests, Protocol (draft)

Status: **DRAFT, not frozen.** Nothing here has been run. It is to be frozen
before any of it touches MUSDB18-HQ.

The behavioural and retrieval protocols test whether a fragment can be
layered on a session. This one would test whether it can follow.

## Design

The product proposes fragments for a session; some are meant to be layered,
others to follow. v1 only tests layering.

- **Pairs**: from each track's mixture, segment A (16 beats) and the segment
  B that follows it (the next 16 beats), on a grid estimated from A and B
  together. Up to three such pairs per track, spread over the track.
- **Scorer under test**: a chord-transition score. Per-beat chord weights
  (`beatgrid.chord_posteriors`) are made key-relative by rotating to the
  segment's estimated tonic; the score of B after A is the weight that a
  transition table gives to moving from A's last two beats to B's first two.
  The table is counted from consecutive beats inside songs of the MUSDB18-HQ
  `train` folder and evaluated on the `test` folder. This is the one place
  in the study where something is fitted, so the split matters here.
- **Comparisons**: `clap_cos_mix`, `chroma_as_is` and `tempo` between A and
  B, and `cocola`.
- **Tests**, each against the true B:
  - *bar shuffle*: B's four 4-beat blocks in a different order. Key, tempo,
    timbre and pitch-class content are unchanged; only the order of the
    harmony differs. Control: the same four blocks cut and rejoined in the
    original order with the same crossfades.
  - *varispeed*: B a semitone up or down by resampling (key and tempo jump
    at the join).
  - *random next*: the B of another track, as the reference.
- **Known weakness**: the grid has beats but no downbeats, so the 4-beat
  blocks may not line up with the real bars. The splice control carries the
  same cuts, which keeps the comparison fair but may weaken the effect.

## Prior work this builds on

Chord-transition scoring for joining segments is not new: Music Cut and
Paste (ISMIR 2013) and MedleyAssistant (2018) both use the transition from
the last beat of one segment to the first beat of the next. Beat-synchronous
chroma matching across transpositions goes back to cover-song identification
(Ellis and Poliner, 2007) and to AutoMashUpper (2013). What this would add is the
bar-shuffle counterfactual with its splice control, applied across pooled
embeddings, a coherence model and classical signals.


## Cost

One pass over the 150 mixtures (segments, grids, features), a few hours on a
laptop CPU.
