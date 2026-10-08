# Verification Status

What Pocket Producer's evaluation pipeline verifies, what it does not, and what we know about the gap.

## Ranking pipeline

### Verified (unit-tested, deterministic)

| Component | What the tests prove | Test file |
|---|---|---|
| Rules ranker (rules-v1) | Tempo/key/intent/novelty/recency/track-gap features score correctly; evidence labels match contributions; limit truncation; empty-candidate edge case; stable tie-breaking by fragment ID | `test_baselines.py`, `test_features.py` |
| Fusion ranker (fusion-5sig-v1) | Closer audio embedding ranks first; tempo breaks audio tie; key signal is zero when session key is absent (Audiotool never provides key); tag Jaccard uses context_tags; candidates without embeddings score zero with no evidence; zero-contribution signals carry no evidence; weight arity check at load | `test_fusion_ranker.py` |
| Audio cosine ranker | Prefers candidate closest to intent; evidence attached; missing embeddings rank last without fake evidence; empty intent raises; scores bounded and sorted; limit respected with stable ties | `test_audio_cosine.py` |
| Mean session ranker | Ranks by similarity to mean of region embeddings; single-region context works; missing region embeddings raises | `test_more_baselines.py` |
| Text cosine ranker | Prefers closest candidate in text space; missing text embedding scores zero without evidence; empty intent raises | `test_more_baselines.py` |
| Recency ranker | Newest fragment ranks first; evidence uses recency code; ties stable by ID and limit respected | `test_more_baselines.py` |
| Harmonic fit | Identical chromas score 1; transposed chromas detected; different quality scores lower; zero/both-zero chromas handled; score in valid range; sine wave peaks at correct chroma bin; silence returns zero | `test_harmonic.py` |
| Role probe | Valid roles returned; aligned embedding classifies correctly; zero embedding yields zero confidence; confidence sums to one; threshold boundary; missing/present/all-filled role gap logic | `test_role_probe.py` |
| Ranking service | Known healthy adapter resolves without fallback; unknown model falls back to rules; unhealthy adapter falls back; adapter exception falls back; response carries server request ID; direct rules request is not marked fallback; model cards listed | `test_service.py` |
| Feature functions | Tempo match: exact=1, close=high, far=0, missing=0, bounded, half/double tempo=0. Key match: case-insensitive, relative mode, fifth mode. Intent match, novelty, recency | `test_features.py` |

### Verified (integration-level)

| Component | What the tests prove | Test file |
|---|---|---|
| Fragment ingest API | Text ingestion lifecycle; empty/oversized input rejected; prompt injection flagged but accepted; XML tag injection stripped; invalid/nonexistent fragment IDs handled; text truncation at max chars; edit creates history | `test_api_integration.py` |
| Rescue score | Single-fragment, high/medium/low score projects; no-emotion-tags edge case; near-complete demo scenario; specific sample calculation | `test_rescue_score.py` |

### Verified (offline evaluation harness)

| Component | What the tests prove | Test file |
|---|---|---|
| Offline eval | Rules scores a constructed example; audio cosine uses precomputed intent embedding; missing intent is a reported skip (not a silent zero); per-participant grouping; unknown model rejected; non-pairwise labels rejected; mean session skips/scores correctly; all preregistered comparison models are scorable; learned models skip without context; ladder IDs without scorers rejected | `test_offline_eval.py` |
| Metrics | Pairwise accuracy: counts correct orderings, tie=0.5, empty rejected. Log loss: bounds enforced, uniform probability is log2. nDCG: graded labels required/computed, perfect order is 1. MRR: requires single positive, computes | `test_metrics.py` |

### Verified (representation/embedding layer)

| Component | What the tests prove | Test file |
|---|---|---|
| CLAP adapter (MS-CLAP) | Audio embedding is finite, unit-norm, 1024-d; text and audio live in comparable space; style scores run on real model | `test_msclap_adapter.py` |
| MERT adapter | Import does not load weights; text tower absent; audio embedding is finite, unit-norm, 768-d; different audio gives different embeddings | `test_mert_adapter.py` |
| Adapter caching | Same audio yields same embedding; different audio yields different embedding; text encoding deterministic; record carries full lineage; NaN output rejected; cache hit skips recompute; different model revision is cache miss | `test_adapters.py` |
| Representation records | Valid record roundtrips; missing revision/input hash rejected; dims mismatch rejected; NaN/Inf vectors rejected; unknown modality rejected; legacy embedding becomes text representation; fragment without embedding returns none | `test_representations.py` |
| Enrichment | Owned fragment gets stored vector; legacy text embedding attached; foreign fragment never leaks a vector; missing/invalid IDs stay none; existing embeddings not overwritten | `test_enrichment.py` |

### Verified (training/research)

| Component | What the tests prove | Test file |
|---|---|---|
| Weak-pair generation | Positive shares source with context; negatives never from context source; context size 2-4; small sources skipped; deterministic given seed; different seed changes sampling; negative types labeled; no source in both splits; split is deterministic; val fraction respected | `test_weak_pairs.py` |
| Model training | Linear model learns above chance; context model trains with finite loss; training is deterministic given seed | `test_training.py` |
| Model ladder | Forward is finite on CPU; region token order invariant; padding does not change output; candidate content changes output; context model under 500k params at full size; ladder capacity strictly increasing; save/load reproduces outputs; checkpoint records param count | `test_model_ladder.py` |
| Ladder adapter | Scores and orders candidates; missing/non-finite/wrong-dimension regions raise; all-unscorable candidates raise; wrong-dim/non-finite candidates skipped; unscorable request falls back to rules; model card has provenance and no filesystem path | `test_ladder_adapter.py` |
| Ladder E2E | Each ladder model serves without fallback; unscorable candidates fall back to rules; model cards expose ladder provenance | `test_ladder_e2e.py` |
| Capacity harness | Reports all three ladder rungs; parameters increase and stay in budget; latencies positive and outputs finite; parameter counts deterministic | `test_capacity_harness.py` |

### Verified (data export/feedback)

| Component | What the tests prove | Test file |
|---|---|---|
| Feedback export | Identity and auth fields stripped; participant ID hashed one-way and stably; research fields kept | `test_feedback_export.py` |
| Zero-shot style scoring | Scores cover fixed vocabulary only; deterministic; scores are cosines in valid range; top styles ordered by score | `test_zero_shot.py` |
| Retrieval | Returns ranked matches for owner only; deleted fragments hard-filtered; k truncates; empty library returns empty; dimension mismatch raises; scores are descending cosines | `test_retrieval.py` |
| Intent parsing | Lowercases/dedupes/caps tags; roles restricted to vocabulary; out-of-range BPM dropped; unparseable key dropped; empty result is none; parses structured response; empty text returns none without API call; failure returns none; cache hits skip second call. Apply: no parsed intent = identity; expands text intent with new tokens only; LLM fills blank BPM/key only; live session values always win; original request not mutated | `test_intent.py` |


## Not verified

These are known gaps. They are listed here so that reviewers can distinguish between "tested and works" and "believed to work but not proven."

| Gap | Why it matters | Mitigation |
|---|---|---|
| End-to-end ranking quality against human preference | Unit tests verify that each signal fires correctly in isolation, but no automated test asserts that the combined ranking output matches what a human producer would choose. The offline eval harness exists and runs, but its labeled dataset is small (formative-scale). | Pairwise annotation protocol is implemented (`/api/ranking/pairs/`); blind labeling prevents rationalization. Pairwise accuracy and nDCG are computed per-participant. We report the current dataset size honestly; significance testing is deferred until the sample is large enough. |
| Session audio embedding quality in production | Adapter tests prove embeddings are finite, unit-norm, and deterministic, but do not verify that the learned embedding space captures musically meaningful similarity for the genres Pocket Producer users actually record. | The bakeoff harness (`test_bakeoff.py`) tests pack co-membership recall as a proxy for musical coherence. MS-CLAP and MERT are published, peer-reviewed models; we verify our adapter wrapping, not the upstream model. |
| Key signal (always zero online) | The fusion ranker's key term carries trained weight but contributes nothing in production because Audiotool sessions never expose key metadata. | The test suite explicitly asserts this: `test_key_signal_zero_when_session_key_none`. The weight is kept rather than zeroed so the signal activates if a future integration provides key. |
| Frontend ranking display | The ranking API returns evidence objects, but no automated test verifies that the frontend renders them correctly or that the user sees the right explanation for each recommendation. | Manual QA during development. The evidence schema is stable (`RankEvidence` in `schemas.py`) and typed end-to-end. |
| Latency under concurrent load | The ranking API has a 2-second timeout and falls back to the rules ranker, but there is no load test proving the timeout fires correctly under realistic concurrency. | The timeout is a standard `asyncio.wait_for`; the fallback path is tested (`test_service.py`). |
| Fragment audio validation | Audio files are accepted if `soundfile` can decode them, but there is no test for corrupt, truncated, or adversarial audio input beyond what soundfile itself rejects. | `soundfile.read` failures are caught and return empty embeddings; the ranking pipeline handles missing embeddings gracefully (scored zero with no evidence). |

## How to run the tests

```bash
cd backend
python -m pytest tests/ -x -q
```

Adapter tests that require model weights (`test_msclap_adapter.py`, `test_mert_adapter.py`) are skipped automatically when weights are not present. Ladder E2E tests require `POCKET_LADDER_DIR` to point at trained checkpoints.
