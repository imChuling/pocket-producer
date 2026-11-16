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
(`research/results-behavioral-v1.md`). The two-signal sum was added after the behavioural report. It is a
design choice to expose harmony and rhythm together, not a demonstrated
improvement over onset alone: `onset_pattern` has higher Recall@1 point
estimates in all three pools (`research/results-retrieval-v1.md`). No paired
interval for that contrast was computed, and no independent product test
has validated incremental value.

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
   correlation of the two slot patterns mapped to [0, 1]. The raw functions
   still match the frozen research definitions. Online availability additionally
   requires four shared sounding beats; rhythm also needs non-flat patterns.
   A mapped value near 0.5 is near-zero correlation, not positive alignment
   evidence. These support rules are engineering guards, not thresholds fitted
   to MUSDB outcomes.

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

- `beat-fit-v1` (local revision `evidence-and-support-v2`): sum of the
  signals standardised over candidates with usable values for each signal.
  No fitted weights. A sole usable measurement contributes its raw value;
  unavailable components contribute zero and are explicitly masked. These
  different support patterns can affect comparability, so inspect masks.
  With no shared sounding beats, candidates do not receive rhythm evidence.
  Bad/unsupported frame records are skipped with a diagnostic; a damaged
  beat log does not invalidate otherwise valid five-signal fusion results.
- Evidence labels state **raw chroma cosine / signed onset correlation and
  shared-beat count**. `RankEvidence.raw_value` carries that measurement;
  `contribution` is the relative ranking term. Both signs and tied zero
  contributions are retained. Neither quantity is a calibrated probability
  that musicians will like a proposal.
- `fusion-5sig-v1`: scores and shipped weights remain five-dimensional.
  Beat measurements are logged after those five; absent beat values have
  zero placeholders **plus** `signal_available=false`. The historical base
  five retain their defined structural-zero conventions for absent key,
  tempo or tags.
- `RankResponse.signal_names` names each vector. Exposure logs persist
  `candidate_signal_names`, `candidate_signals` and
  `candidate_signal_available`. Training aligns by names, not vector length,
  and refuses ambiguous extended legacy rows or unavailable trained signals.

## Capability and rollout boundary (2026-11-16)

| Capability | State |
|---|---|
| Five-signal fusion and reversible DAW insert | Existing implementation; current live revision not verified in this remediation |
| Beat-fit, frame ingest, bounded grid, availability/evidence fixes | Local implementation and tests; not deployed |
| Existing-fragment frame backfill | Script exists; not run on production |
| Five-signal feedback training | Offline research workflow, tested artifact-to-loader-to-score; not automatic online learning |
| Seven-signal feedback training | Research only; artifact marked nondeployable, distinct identity; online five-signal loader refuses it |
| Demo / cost changes | Five commits from `cost-guard` integrated locally; deployment not performed |

The behavioural guardrail first validates nonempty unique pairs, applicable
perturbations, finite scores, at least two tracks and usable P1–P5/gain.
An optional explicit manifest checks exact pair and track identities. The
original cache has no historical manifest; a newly created inventory is
not retroactive proof of original extraction. Performance rules then protect
only endpoints the baseline already passes (on this store mainly P3), plus
gain direction sensitivity. Passing is not a quality floor for every endpoint
or evidence of preference benefit. Repeated filtering on MUSDB makes it a
development set.

A future deployment needs a real DAW playback comparison, a separately
reviewed production backfill and an explicit serving contract for any new
weight dimensionality. A seven-weight research artifact must not be copied
into the five-signal deployment path. No such rollout was executed here.

## Open questions

- Whether the onset slot count (8 per beat) is too fine for loops recorded
  without a click.
- Regions that loop or start inside their sample are placed as if they play
  from the start; supporting them needs the sample offset and loop length
  from the document.
- Cost: frame analysis adds roughly a second per fragment at ingest and per
  uploaded sample in `/session-embed` on the current CPU instance.
