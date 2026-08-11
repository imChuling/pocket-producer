# Model Card — Pocket Producer Ranking System

## Overview

Pocket Producer ranks a user's personal audio fragments by **continuation utility**: how useful each fragment would be as the next creative step in a live music production session. The system is _not_ a general-purpose music recommender — it operates over a single user's private library, conditioned on the state of an open Audiotool project.

## Capacity Ladder

All models share a hard parameter budget of **500,000 trainable parameters** and run on CPU at inference time.

| Model | Parameters | Latency (p50) | Latency (p95) | Input |
|---|--:|--:|--:|---|
| `linear-v1` (L0) | 2 | 1.3 ms | 2.1 ms | Cosine similarity + bias (trained FSLD config, `structured_dim=0`) |
| `deepsets-v1` (L1) | 295,425 | 1.7 ms | 2.2 ms | Set of CLAP embeddings → phi/rho |
| `pocketrank-context-v1` (L2) | 400,449 | 15.9 ms | 21.9 ms | Shared projection + 2-layer Transformer + attention pool + low-rank interaction |

Measured on Apple M-series CPU, batch size 32, 32 context tokens, from the exact trained checkpoint config (`artifacts/pocketrank-context-fsld-v1/config.json`). The full-feature architecture (`structured_dim=18`) adds 18 structured-feature weights to `linear-v1` (20 params) and slightly more to the others; it is not what the FSLD checkpoints train or serve.

## Baselines (no learned parameters)

| Baseline | Description |
|---|---|
| `rules-v1` | Weighted combination of 6 deterministic [0,1] features (tempo match, key match, track gap, intent match, novelty, recency). Always-available fallback. |
| `recency-v1` | Most-recently-created first. |
| `text-only-v1` | Voyage voyage-3 cosine between intent text and candidate text embedding. |
| `audio-cosine-v1` | MS-CLAP cross-modal: intent text encoded in audio space → cosine vs candidate audio embeddings. |
| `mean-session-v1` | Cosine to mean of CLAP embeddings of audio regions currently in the session. Degrades gracefully when no session audio is available. |

## Audio Representations

Two frozen backbones were evaluated on 2,558 FSLD items:

| Backbone | Dims | P1 Recall@10 | P2 Genre Acc | P2 Role Acc | License |
|---|--:|--:|--:|--:|---|
| MS-CLAP 2023 | 1024 | 0.692 | 0.384 | 0.533 | MIT (code) |
| LAION-CLAP music | 512 | 0.713 | 0.415 | 0.556 | CC0 (code); training data audit incomplete |

**Deployment default**: MS-CLAP 2023. LAION-CLAP wins all probes but its training data license audit is not yet complete. Representation quality and deployment eligibility are separate decisions.

Revision pinning: every stored vector carries `model_id`, `revision` (sha256 of weights), `input_sha256`, `dims`, and `pooling` method.

## Training Data

### Weak pretraining (FSLD)

- 1,755 leave-one-out pairs from 2,558 annotated FSLD items
- Three negative types: easy random, hard tempo/key match, hard cosine-similar
- Split: 1,236 train / 519 val (per-source grouped, deterministic seed 20260725)
- Label type: **weak** (same-pack membership as proxy for continuation utility)
- Per-item licenses classified from metadata: cc-by 4,827 / cc0 3,230 / cc-by-nc 1,215 / sampling-plus 221

### Human labels

- Pairwise annotation protocol preregistered (research/protocol.md)
- Annotation interface: blind A/B comparison with structured reason codes and confidence scale
- Gate criterion: L2 must exceed cosine baseline on human pairwise accuracy to deploy

## Evaluation

- **Primary metric**: pairwise accuracy (fraction of pairs where the model ranks the human-preferred candidate higher)
- **Grouping**: per-participant, to prevent a single prolific annotator from dominating
- **Label-type enforcement**: code raises `ValueError` if labels are not `pairwise`
- **Honest skips**: models that cannot score an example (missing embeddings, no session context) skip it; skips are counted, not zeroed

### Weak-label results (FSLD, val split)

| Model | Val Pairwise Accuracy | Train Examples | Val Examples |
|---|--:|--:|--:|
| `linear-v1` | **0.880** | 1,236 | 519 |
| `deepsets-v1` | 0.720 | 1,236 | 519 |
| `pocketrank-context-v1` | 0.743 | 1,236 | 519 |

**Key finding**: the two-parameter cosine-plus-bias baseline beats both learned models on weak labels. The benchmark predominantly rewards embedding proximity, so it cannot establish validity for continuation utility — which is why the preregistered human evaluation exists. Whether learned capacity helps on the real task is decided by human labels, not these numbers.

## Limitations

- **No personalization**: the system does not adapt to individual user preferences over time. This is a deliberate design constraint; the preregistered protocol requires temporal held-out learning curve support before enabling adaptation.
- **Session representation is flat**: the current `SessionFingerprint` captures tempo, track count/types, playhead, and mean audio embedding but not per-region role, temporal position, or pitch class structure.
- **Small evaluation scale**: human pairwise labels are in pilot quantities. Statistical power is limited; results are reported honestly with sample sizes.
- **Backbone audit incomplete**: LAION-CLAP music training data provenance has not been fully verified for commercial deployment.

## Ethical Considerations

- The system ranks only within a user's own library; it never surfaces other users' content.
- No creativity claims: short-term retrieval experiments cannot support assertions about enhancing creativity (per ICCC 2018 evaluation guidelines).
- Audio from user sessions is CLAP-encoded for ranking only; raw audio is never stored by the backend or sent to third parties.
- Feedback data export uses an allowlist of named fields; user IDs are one-way hashed before leaving the database.

## Intended Use

Session-conditioned fragment retrieval during live music production in Audiotool. Not intended for general music recommendation, playlist generation, or use outside the Pocket Producer application context.

## Contact

Chuling Li — chuling.li.cs@gmail.com
