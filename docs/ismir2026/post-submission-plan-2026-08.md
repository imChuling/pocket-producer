# Post-Submission Plan (2026-08-24 → camera-ready)

LBD submitted 2026-08; decision window ~6 weeks. Everything here is
solo-executable (no external participants). House discipline applies
throughout: freeze a protocol file BEFORE any held-out evaluation runs;
every new artifact carries a provenance.json; 7.8 pp remains
"configuration sensitivity", never causal.

## Task 1 — Third representation + more seeds (sensitivity grid)

Goal: test whether the fusion-vs-cosine swing (7.8 pp across LAION-CLAP
and MS-CLAP) is a two-model accident or a pattern.

Model choice: MERT-v1-95M (audio-only SSL). The 5 fusion signals
(audio_cos_mean, audio_cos_max, tempo, key, tag_jaccard) need only the
audio tower, so a text-tower-free model is fine. Verify license before
downloading and record it in DATA_CREDITS.md (same audit as MS-CLAP).

Steps, in order:

1. Freeze `research/protocol-mert-sensitivity-v1.md` (mirror
   protocol-msclap-sensitivity-v1.md). Pre-specify: pooling strategy
   (mean over time of a pre-chosen layer; pick and lock BEFORE running),
   reuse of the frozen split (seed 20260810), SEEDS, metrics, and the
   rule that held-out is evaluated exactly once after dev decisions lock.
2. New adapter `backend/ranking/adapters/mert.py`, following
   `msclap.py`: lazy load, RepresentationModelCard, revision pinned to
   checkpoint hash. Unit test alongside existing adapter tests.
3. Register in `make_adapter` (`research/embed_fsld_subset.py`).
4. Embed the corpus → `research/data/fsld/items_mert_packonly.jsonl`.
   IMPORTANT: do not re-derive item selection; intersect with the item
   ids in `items_laion-clap-music_packonly.jsonl` so all three
   representations share the identical 1,797 items / 605 sources.
   Then split off `..._train.jsonl` using the frozen split.
5. Dev set: `run_fusion.py` on the train side → `artifacts/fusion-mert/`.
6. Held-out: add `--mode mert` to `run_heldout_correction.py`
   (signal indices unchanged) → `artifacts/mert-sensitivity/` with
   provenance.json (artifact SHA, split SHA, n_bootstrap=10000,
   alpha=0.05, source-level resampling, seeds).
7. Seed extension: append 5 new seeds to the existing 5 (keep the
   published 5-seed artifacts untouched; write 10-seed runs to
   `artifacts/*-seeds10/`). Rerun LAION + MS-CLAP + MERT so all three
   columns have 10 seeds.
8. Analysis: per-representation fusion-vs-cosine hard_similar delta and
   its seed spread. Question answered: does a third representation also
   move the conclusion, and by how much.

Compute: embedding ~1.8k items ≤30 s each; run on NBE_1 strictly under
/data3/shanliantian/lcl (sync FSL10K.zip + scripts there, sync jsonl
back). CPU-local is a fallback for the 95M model.

## Task 2 — Key-axis investigation

Background: key does not replicate under held-out LOSO (−0.12 pp
hard_similar, sign unstable); dev-set result is descriptive only.
Two hypotheses: (a) annotation keys are noisy, (b) exact-match scoring
is too brittle. Either a fix or a documented cause is a publishable
outcome.

1. Freeze `research/protocol-key-audit-v1.md` with the decision rules
   below stated in advance.
2. Step A, label quality: `research/audit_key_labels.py`. Estimate key
   from audio for ~100 stratified items using the existing
   `harmonic_probe.chroma_from_audio` + Krumhansl-Schmuckler template
   matching; compare against FSL10K annotation key. Report agreement
   rate and the confusion structure (relative major/minor swaps,
   perfect-fifth errors) → `artifacts/key-audit/key_audit.json`.
3. Step B, tolerant matching: implement key_match variants in
   `backend/ranking/features.py` behind a parameter (exact = current;
   +relative major/minor; +fifth neighbors, i.e. Camelot-adjacent).
   Rerun dev LOSO (`run_ablation.py`) per variant. Dev only; no
   held-out until one variant is locked.
4. Step C, feature-source swap: replace annotation key with
   audio-estimated key, rerun dev 5-split + (once, after locking)
   held-out LOSO via `loso_heldout.py` → `artifacts/key-audio-est/`.
5. Outcome framing: "key replicates under X" or "key failure traced to
   Y". Both go in the camera-ready §4 or the next paper.

## Task 3 — Telemetry (dogfood-first)

Already in place: `FeedbackEvent` (preview/accept/reject/insert/undo,
rank_position, model_id), `/feedback` endpoint (Firebase-token user_id
only), frontend queue (`sendFeedbackQueued`), `ranking_feedback`
collection.

Missing pieces:

1. Exposure logging (the denominator). In the recommend route, persist
   each served list to a new `ranking_requests` collection:
   request_id, user_id (from verified token), project_id,
   model_id_requested, model_id_served, ordered fragment_ids,
   created_at. Absolutely no OAuth tokens, no Authorization headers,
   no audio payloads (existing constraint). Add tests in
   `backend/tests/ranking/`.
2. Config attribution: verify the user-selectable fusion toggle
   actually flows into `response.model_id` end to end (frontend
   defaults to "rules-v1"); acceptance metrics bucket by model_id.
3. Analysis script `research/analyze_feedback.py`: joins
   ranking_requests × ranking_feedback; per model_id computes
   acceptance rate (accepts / exposed lists), undo rate (undos /
   inserts), preview-then-reject rate, mean accepted rank; bootstrap
   CIs resampled by session. Output `artifacts/telemetry-pilot/`.
4. Dogfood cadence: use the app in real sessions ~3×/week; data
   accumulates during the wait with zero external dependencies. The
   pipeline being proven end-to-end is the deliverable; the numbers are
   a bonus.

## Task 4 — Housekeeping

1. Production OAuth callback: register the deployed `/audiotool`
   redirect URI for the Audiotool client (currently only local is
   registered), set the prod env var (client ID stays out of git;
   .env.local is gitignored), verify the authorize round-trip on the
   deployed site. Prerequisite for any live demo.
2. Screencast script now, recording later (per workflow preference):
   `docs/demo/screencast-script.md` covering connect → propose →
   preview → insert → undo → switch ranker. Unblocks C2/C3 capture.
3. Camera-ready checklist (execute only if accepted), add to
   submission-checklist.md: drop `submission` from
   `\usepackage[lbd,submission]{ismir}` (removes line numbers, switches
   copyright notice), fill real author name in copyright, delete
   "rather than default" at the end of §2.1, re-run checker + build.sh,
   verify 3 pages.
4. Doc drift: `research/README.md` says 152 assertions twice; checker
   is now 151. Fix both mentions.

## Sequencing (6 weeks)

- W1: protocols frozen (Task 1.1, 2.1); MERT adapter + embedding run;
  exposure logging + tests live so dogfood data starts accumulating.
- W2–3: MERT dev + held-out, 10-seed extension; key Steps A/B.
- W4: key Step C; first pass of analyze_feedback.py on pilot data.
- W5: consolidate artifacts + provenance; update research/README.md
  with new commands; fix doc drift.
- W6: buffer; screencast script; camera-ready prep staged.

Deferred (needs other people): listening study over
fusion-vs-rules disagreement pairs; revisit post-decision.
