# Design: beat-synchronous signals online

Status: proposal, not implemented. No product code changes until reviewed.

## Goal

Add two signals from the behavioural tests to the deployed fusion:
`chroma_beat_aligned` (harmony in step with the session's beats) and
`onset_pattern` (rhythm in step with the session's beats). On MUSDB18-HQ
they pass P1, P3 and P4 (`chroma_beat_aligned` also P2; `onset_pattern`
also P5), where the deployed fusion passes only P3
(`research/results-behavioral-v1.md`). Weights would be learned from logged
decisions with `research/finetune_from_feedback.py --extra-signals
chroma_beat_aligned,onset_pattern`, behind the behavioural guardrail
(`research/compat_tests/guardrail.py`).

## What the research code computes

Both signals compare a candidate with a context on the context's beat grid
(`research/compat_tests/signals.beat_scores`):

1. Frame analysis of each clip at 22050 Hz, hop 512: 12-bin chroma, onset
   strength and RMS per frame (`beatgrid.frames`). This is computed once per
   clip and does not depend on any grid.
2. A constant-tempo grid for the context (`beatgrid.grid_from_frames`).
3. Both clips' frames pooled on that grid: mean chroma per beat
   (`pool_chroma`) and peak onset strength in 8 slots per beat
   (`pool_onsets`).
4. `chroma_beat_aligned` = mean per-beat chroma agreement
   (`progression.aligned_fit`, 0 with fewer than 4 shared non-silent beats);
   `onset_pattern` = correlation of the two slot patterns mapped to [0, 1].

The candidate is only ever needed as frames, so it can be analysed at ingest
and pooled on any session's grid at request time.

## Ingest (per fragment)

- After decoding, in the same step that writes `representations.chroma`,
  compute `beatgrid.frames` on one 10 s window and store it as
  `representations.beat_frames`:
  `{revision, window_start_seconds, hop_seconds, chroma: 12 x n (float16,
  base64), onset: n, rms: n}`. About 430 frames, roughly 12 KB per fragment.
- Window: the 10 s with the most onset strength, so loops longer than 10 s
  are judged on their busiest part. Clips shorter than 10 s use the whole
  clip.
- `scripts/backfill_representations.py` gains the same step for existing
  fragments.

## Session side (`/session-embed`)

The grid must come from the session as it plays, not from separate samples.

- Preferred: the session's tempo and the regions' timeline positions are
  known exactly from the Nexus document, so the frontend renders the first
  10 s of the session mix with `OfflineAudioContext` (regions placed at their
  positions) and sends that one clip alongside the per-sample uploads it
  sends today. The backend computes `frames` and the grid on it and pools
  the session's own beat chroma and onset slots.
- The grid's tempo should be replaced by the project tempo when one is
  known; only the phase is estimated.
- Response gains `session_beats: {bpm, beat_times, beat_chroma (n x 12),
  onsets (n x 8)}`, which the frontend passes back in the rank request.

## Rank request and scoring

- `SessionFingerprint` gains `session_beats` (above), optional.
- `FragmentCandidate` gains `beat_frames` (from `representations.beat_frames`
  via `ranking/enrichment.py`), optional.
- `FusionRanker` pools each candidate's frames on the session grid and adds
  the two signals. Missing on either side means 0 for both, the convention
  the other signals already use.
- Candidates are inserted at the start of the timeline today, so the
  candidate's beat 0 is aligned with the grid's first beat; the pooled
  features should be computed with the same alignment.

## Weights, logging and rollout

- `SIGNAL_NAMES` becomes the list in the weights file instead of a constant,
  and `load_weights` accepts any length matching that list. Older 5-signal
  files keep working with the two new weights treated as absent.
- `ranking_requests` gains `candidate_signal_names` next to
  `candidate_signals`, so lists logged before and after the change are not
  mixed (`finetune_from_feedback.py` already drops vectors of the wrong
  length).
- Rollout: log the two signals first with zero weight, so decisions start
  accumulating with the new features while ranking is unchanged; fine-tune
  once there are enough pairs; ship only a guardrail-accepted weights file.

## Open questions

- Where the session mix is rendered: in the browser (no extra upload size
  per sample, but more client work) or on the server from region positions
  sent with the samples.
- Whether the onset slot count (8 per beat) is too fine for loops recorded
  without a click.
- Cost: frame analysis adds roughly a second per fragment at ingest and per
  session request on the current CPU instance.
