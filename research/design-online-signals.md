# Design: beat-synchronous signals online

Status: implemented (`backend/ranking/beat_sync.py`,
`backend/ranking/beat_fit_ranker.py`). Not deployed yet; `beat-fit-v1` is
user-selectable and not the default, and `fusion-5sig-v1` scores exactly as
before.

## Goal

Bring two signals from the behavioural tests online:
`chroma_beat_aligned` (harmony in step with the session's beats) and
`onset_pattern` (rhythm in step with the session's beats). On MUSDB18-HQ
they pass P1, P3 and P4 (`chroma_beat_aligned` also P2; `onset_pattern`
also P5), where the deployed fusion passes only P3
(`research/results-behavioral-v1.md`). In the retrieval study their
standardised sum was the strongest training-free combination
(`research/results-retrieval-v1.md`); it was added after the behavioural
report, so it is an observation, not a tested claim.

Two uses:

1. `beat-fit-v1`, a new ranker that scores with the two signals directly.
2. `fusion-5sig-v1` logs them next to its own five, so fusion weights that
   include them can later be learned from logged decisions with
   `research/finetune_from_feedback.py --extra-signals
   chroma_beat_aligned,onset_pattern`, behind the behavioural guardrail
   (`research/compat_tests/guardrail.py`).

## What is computed

The product code mirrors `research/compat_tests` (`beatgrid`, `progression`,
`signals`) without importing it; `backend/tests/ranking/test_beat_sync.py`
checks the two agree numerically.

1. Frame analysis of a clip's first 10 s at 22050 Hz, hop 512: 12-bin
   chroma, onset strength and RMS per frame (`beat_sync.frames`). Silence
   (RMS below -50 dBFS) gives no frames.
2. Pooling on a beat grid: mean chroma per beat (zero for beats below
   -50 dBFS), L2-normalised, and peak onset strength in 8 slots per beat,
   scaled to [0, 1].
3. `chroma_beat_aligned` = mean per-beat chroma agreement over beats where
   both sides sound (0 with fewer than 4 such beats); `onset_pattern` =
   correlation of the two slot patterns mapped to [0, 1] (0 if either is
   flat).

## The session grid

The grid is never estimated from audio. It comes from the project tempo in
the Nexus document: beats start at timeline zero with period 60 / bpm, and
only the whole beats inside the first 10 s are used. Without a tempo there
is no grid and the signals are missing.

- The frontend reads each audio region's `positionTicks` and
  `durationTicks` (3840 ticks per beat) and sends, with the per-sample
  uploads `/session-embed` already receives, the project `bpm` and
  `placements`: one list per uploaded file of
  `{start_beats, duration_beats}`.
- The backend analyses each uploaded sample once and places a copy at each
  of its regions, cut at the region's end. Overlapping regions combine per
  beat: chroma is summed weighted by each region's RMS in that beat and then
  normalised; onset slots take the strongest region.
- Region loop and sample-offset settings are ignored: each region plays its
  sample from the start.
- The response gains `session_beats: {bpm, beat_times, beat_chroma
  (beats x 12), onsets (beats x 8, flattened)}`, which the frontend sends
  back in `RankRequest.session.session_beats`.

## The candidate side

- Ingest (`ranking/ingest.py`) writes `representations.beat_frames` next to
  `representations.chroma`: frames of the fragment's first 10 s, stored as
  float16 base64 with `revision: beat-frames-v1`, about 12 KB per fragment.
  The opening is used, not the busiest part, because candidates are
  inserted at the start of the timeline and heard from beat 0.
- When only model-free records are missing, ingest writes them without
  re-running CLAP.
- `scripts/backfill_representations.py` has the same step for existing
  fragments. It has not been run on production.
- `ranking/enrichment.py` attaches the stored record to
  `FragmentCandidate.beat_frames`; the candidate's frames are pooled on the
  session grid at request time.

## Rankers and logging

- `beat-fit-v1`: score = the two signals, each standardised over the
  scorable candidates in the request, summed. No weights are fitted.
  Candidates without frames, or with both signals at 0, are skipped; if none
  remain, or the session has no beat data, it raises
  `InsufficientContextError` instead of serving evidence-free proposals.
  Evidence codes `beat_harmony` and `beat_rhythm` carry the positive
  standardised parts.
- `fusion-5sig-v1`: unchanged scores and weights. Its signal vectors gain
  the two values (0 when missing on either side) after the five it scores
  with.
- `RankResponse.signal_names` names the vector, and `ranking_requests` logs
  it as `candidate_signal_names` next to `candidate_signals`, so vectors
  logged before and after the change are not mixed
  (`finetune_from_feedback.py` already drops vectors of the wrong length).

## Rollout

Deploy with `beat-fit-v1` selectable and fusion unchanged, run the backfill
for existing fragments, and let decisions accumulate with the seven logged
signals. Fine-tune once there are enough pairs; ship only a
guardrail-accepted weights file.

## Open questions

- Whether the onset slot count (8 per beat) is too fine for loops recorded
  without a click.
- Regions that loop or start inside their sample are placed as if they play
  from the start; supporting them needs the sample offset and loop length
  from the document.
- Cost: frame analysis adds roughly a second per fragment at ingest and per
  uploaded sample in `/session-embed` on the current CPU instance.
