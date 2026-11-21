# Design: beat-synchronous signals online

The deployed `beat-fit-v1` is selectable. This checkout revises its onset
measurement and opening-window sample selection. Deployment of this revision
has not been verified.

## Goal

Bring two signals from the behavioural tests online:
`chroma_beat_aligned` (harmony in step with the session's beats) and
`onset_pattern` (rhythm in step with the session's beats). On MUSDB18-HQ
they pass P1, P3 and P4 (`chroma_beat_aligned` also P2; `onset_pattern`
also P5), where the deployed fusion passes only P3
(`research/results-behavioral-v1.md`). The two-signal sum was added after the
behavioural report. Showing harmony and rhythm together is a design choice,
not a measured improvement: `onset_pattern` alone has higher Recall@1 point
estimates in all three pools (`research/results-retrieval-v1.md`), no paired
interval for that difference was computed, and no product test has shown
that adding harmony helps.

Two uses:

1. `beat-fit-v1` scores harmony and rhythm together. The local revision restricts rhythm to shared sounding beats.
2. `fusion-5sig-v1` logs them next to its own five, so fusion weights that
   include them can later be learned from logged decisions with
   `research/finetune_from_feedback.py --extra-signals
   chroma_beat_aligned,onset_pattern`, behind the behavioural guardrail
   (`research/compat_tests/guardrail.py`).

## What is computed

The product and research implementations share frame analysis, beat pooling
and the full-grid signal definitions. `backend/tests/ranking/test_beat_sync.py`
checks their numerical agreement.

1. Frame analysis of a clip's first 10 s at 22050 Hz, hop 512: 12-bin
   chroma, onset strength and RMS per frame (`beat_sync.frames`). Silence
   (RMS below -50 dBFS) gives no frames.
2. Pooling on a beat grid: mean chroma per beat (zero for beats below
   -50 dBFS), L2-normalised, and peak onset strength in 8 slots per beat,
   scaled to [0, 1].
3. `chroma_beat_aligned` = mean per-beat chroma agreement over beats where
   both sides sound (0 with fewer than 4 such beats); `onset_pattern` =
   full-grid Pearson correlation of the two slot patterns mapped to [0, 1].
   The frozen MUSDB comparisons and fusion logs use this full-grid signal.
4. Local Beat Fit computes `onset_pattern_shared_beats` from the eight slots
   of each beat where both chroma rows have nonzero norm after RMS gating.
   Both the flatness check and the correlation use those same slots. At
   least four shared beats and two varying patterns are required for rhythm
   evidence. A signed correlation of zero maps to a ranking input of 0.5.

In a synthetic 120 BPM opening, the onset strengths rise across each beat
in one part and fall in the other. Both play for four beats and rest for
sixteen. Their full-grid correlation is +0.30. On the four sounding beats
it is −1.00. If either part has constant onset strength on those beats,
the local ranker reports rhythm as unavailable. The signed value describes
whether accents coincide. A musician may still prefer alternating accents.
The frozen retrieval and behavioural results do not evaluate this variant.

## The session grid

The grid is never estimated from audio. It comes from the project tempo in
the Nexus document: beats start at timeline zero with period 60 / bpm, and
only whole beats inside the first 10 s are used. The supported online tempo
range is finite 20–360 BPM: at most 60 beats / 480 onset slots. API, schema
and grid helpers bound these inputs before allocation. Without supported
tempo the helper returns no grid; malformed API input is rejected.

- The frontend reads each audio region's `positionTicks` and
  `durationTicks` (3840 ticks per beat) and sends, with the per-sample
  uploads `/session-embed` already receives, the project `bpm` and
  `placements`: one list per uploaded file of
  `{start_beats, duration_beats}`.
- For local Beat Fit, only readable placements that start before the
  opening grid's final boundary qualify. The frontend takes the first eight
  distinct samples among those placements in document order and sends their
  in-window placements. At 70 BPM, for example, the last whole beat ends at
  beat 11, about 9.43 s. A region beginning on that boundary contributes
  nothing. More than eight qualifying samples still gives an approximation
  of the arrangement. Other audio rankers keep the session-wide selection.
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

- `beat-fit-v1` (local revision `shared-beat-onsets-v4`): sum of the
  signals standardised over candidates with usable values for each signal.
  With several candidates, a signal needs two measurements to affect their
  order. A rhythm measurement available for just one candidate still appears
  on its card. When only one candidate can be scored, its raw measurements
  supply its score. Missing measurements are masked in the log.
  With no shared sounding beats, candidates do not receive rhythm evidence.
  Bad/unsupported frame records are skipped with a diagnostic; a damaged
  beat log does not invalidate otherwise valid five-signal fusion results.
- Evidence labels state **raw chroma cosine / signed onset correlation and
  shared-beat count**. `RankEvidence.raw_value` carries that measurement;
  `contribution` is the relative ranking term. Both signs and tied zero
  contributions are retained. Neither quantity is a calibrated probability
  that musicians will like a proposal.
- `fusion-5sig-v1`: scores and shipped weights remain five-dimensional.
  Historical full-grid `onset_pattern` and beat chroma are logged after those
  five. The Beat Fit revision uses its own rhythm signal name so logs from
  the two definitions remain distinguishable. Absent beat values have
  zero placeholders **plus** `signal_available=false`. The historical base
  five retain their defined structural-zero conventions for absent key,
  tempo or tags.
- `RankResponse.signal_names` names each vector. Exposure logs persist
  `candidate_signal_names`, `candidate_signals` and
  `candidate_signal_available`. Training aligns by names, not vector length,
  and refuses ambiguous extended legacy rows or unavailable trained signals.

## Capability and rollout boundary

| Capability | State |
|---|---|
| Five-signal fusion and reversible DAW insert | Deployed; fusion is selectable, `rules-v1` is the default |
| Beat-fit, frame ingest, bounded grid, availability/evidence fixes | Deployed; `beat-fit-v1` is selectable |
| Shared-beat onset scoring and selection of opening samples before the cap | Local revision with synthetic regression tests. Deployment unverified |
| Existing-fragment frame backfill | Script exists; not run on production |
| Five-signal feedback training | Offline research workflow, tested artifact-to-loader-to-score; not automatic online learning |
| Seven-signal feedback training | Research only; artifact marked nondeployable, distinct identity; online five-signal loader refuses it |
| Demo / cost changes | Daily LLM quota and scale to zero are deployed; the read-only demo account is built but switched off |

The behavioural guardrail first checks its inputs: non-empty unique pairs,
perturbations that apply, finite scores, at least two tracks and usable
P1 to P5 and gain results. An optional manifest pins the exact pairs and
tracks. The original cache had no manifest of its own, and one made later
cannot prove how the features were first extracted. After those checks the
guardrail only protects the endpoints the baseline already passes (on this
store mostly P3) and the direction of the gain test. Passing it is not a
minimum standard for every endpoint, and it says nothing about what musicians
prefer. Because models have been filtered on MUSDB repeatedly, it now works
as a development set.

Before learned weights that include the beat signals go live, they need a
comparison against real DAW playback, a reviewed backfill of production
fragments and a serving format for the extra weights. A seven-weight research
file must not be copied into the five-signal path; none has been.

## Open questions

- Whether the onset slot count (8 per beat) is too fine for loops recorded
  without a click.
- Regions that loop or start inside their sample are placed as if they play
  from the start; supporting them needs the sample offset and loop length
  from the document.
- Cost: frame analysis adds roughly a second per fragment at ingest and per
  uploaded sample in `/session-embed` on the current CPU instance.
