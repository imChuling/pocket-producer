# Model Card: Pocket Producer Ranking System

## Current status

The live default is `rules-v1`. `fusion-5sig-v1` and `beat-fit-v1` are
deployed and can be chosen in the panel; the deployed fusion scores five
signals. Beat Fit only scores fragments uploaded since it shipped, because
older fragments have not been backfilled with beat frames. The
capacity-ladder models described below are research models and are not
deployed. Training from logged feedback exists only as an offline prototype;
its seven-signal variant is research-only and the online loader refuses it.
What is and is not deployed is listed in the
[design notes](research/design-online-signals.md).

None of the experiments measure whether musicians prefer the suggestions or
whether the tool helps them create; they use perturbed stems, stem retrieval
and pack membership. In retrieval, adding chroma to onset patterns gave no
measurable improvement over onset alone. `COCOLA_HP_v1` was trained on
MoisesDB, Slakh2100 and CocoChorales, not MUSDB18-HQ as an earlier version
of the protocols said (see their errata), and nobody has checked its
training files for overlap with the evaluation data.

A later study ran retrieval the other way round: given one stem, find the
context it came from among 50 that are missing the same stem type.
Beat-aligned chroma plus onset pattern picked the right context first for
54.0% of stems [49.6, 58.4], MS-CLAP cosine for 14.1% and the deployed fusion
for 20.7% (`research/results-assignment-v1.md`). This is evidence about fit,
which matters for ranking, not about grouping. It reuses the recordings of
the earlier studies, the onset combination was chosen after seeing them, the
stems are studio recordings with a steady beat, and one of its seven
predictions (A1) failed.

## Overview

Pocket Producer proposes fragments from a user's private library for an open
Audiotool session. Its intended goal is continuation utility; the implemented
similarity and musical-feature scores are proxies, and current experiments
do not establish how useful musicians will find the recommendations.

## Capacity Ladder

All models share a hard parameter budget of **500,000 trainable parameters** and run on CPU at inference time.

| Model | Parameters | Latency (p50) | Latency (p95) | Input |
|---|--:|--:|--:|---|
| `linear-v1` (L0) | 2 | 1.3 ms | 2.1 ms | Cosine similarity + bias (trained FSLD config, `structured_dim=0`) |
| `deepsets-v1` (L1) | 295,425 | 1.7 ms | 2.2 ms | Set of CLAP embeddings → phi/rho |
| `pocketrank-context-v1` (L2) | 400,449 | 15.9 ms | 21.9 ms | Shared projection + 2-layer Transformer + attention pool + low-rank interaction |

Measured on Apple M-series CPU, batch size 32, 32 context tokens, from the exact trained checkpoint config (`artifacts/pocketrank-context-fsld-v1/config.json`). The full-feature architecture (`structured_dim=18`) adds 18 structured-feature weights to `linear-v1` (20 params) and slightly more to the others; it is not what the FSLD checkpoints train or serve.

## Baselines (no learned parameters)

Nine rankers are registered in the default deployment (with `POCKET_ENABLE_CLAP=1` and the fusion weights present, as deployed): `rules-v1`, `recency-v1`, `mean-session-v1`, `text-only-v1`, `audio-cosine-v1`, `role-gap-v1`, `harmonic-fit-v1`, `beat-fit-v1` and `fusion-5sig-v1`. The eight without fitted weights are listed here; `fusion-5sig-v1`, whose five weights were fitted on pack co-membership, is covered under Grouping and Limitations.

| Baseline | Description |
|---|---|
| `rules-v1` | Weighted combination of 7 deterministic [0,1] features (tempo match, key match, role gap, intent match, tag novelty, tag overlap with the session's inserted fragments, recency). Roles already in the session are inferred from the tags of inserted fragments, since the host DAW reports track kinds, not musical roles; when no role is known, as in a freshly opened project that may already hold untagged parts, role gap is not scored. Always-available fallback and the default. |
| `harmonic-fit-v1` | Transpose-invariant cross-correlation between the session's mean chroma and each candidate's 12-dim chroma; both computed at encode time (session) and ingest (candidate). It measures similarity after the best transposition, not fit as played: it is blind to transposition in the behavioural tests (P2 0.49), and the product never transposes. Silent candidates or sessions (all-zero chroma) are not scored. |
| `beat-fit-v1` | Beat-synchronous chroma agreement plus onset-pattern correlation on the project's beat grid, each standardised over the request's candidates; no fitted weights. Needs the project tempo, region positions and stored `representations.beat_frames`; fragments without stored frames are left out. |
| `role-gap-v1` | Zero-shot CLAP instrument-role probe; scores candidates that fill a role the session regions lack. |
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
- Per-item licenses classified from metadata, counted over the full 9,493-item manifest (`DATA_CREDITS.md`), not over the 2,558 annotated items or the pack-only training subset: cc-by 4,827 / cc0 3,230 / cc-by-nc 1,215 / sampling-plus 221. The pack-only train split that the served fusion weights were fitted on (1,389 loops) is cc-by 635 / cc0 547 / cc-by-nc 129 / sampling-plus 78 (`DATA_CREDITS.md`).

### Human labels

No human evaluation is part of the results: every reported result uses proxy labels (pack co-membership) or controlled perturbations.

The only check now wired into code is narrower: when fusion weights are refit from logged feedback, the new weights must pass the behavioural guardrail (`research/compat_tests/guardrail.py`), or `research/finetune_from_feedback.py` writes no weights. It covers that one flow only, not other models or deployment paths, and it does not stand in for human preference data.

## Evaluation

- **Metric**: pairwise accuracy (fraction of pairs where the model ranks the preferred candidate higher). All results below use weak labels; no human pairwise labels are in them.
- **Grouping**: the harness can group pairs by hashed participant so one person's labels would not dominate; it serves logged feedback, and no reported result uses it
- **Label-type enforcement**: code raises `ValueError` if labels are not `pairwise`
- **Skips**: a model that cannot score an example (missing embeddings, no session context) skips it, and skips are counted rather than scored as zero

### Weak-label results (FSLD, val split)

| Model | Val Pairwise Accuracy | Train Examples | Val Examples |
|---|--:|--:|--:|
| `linear-v1` | **0.880** | 1,236 | 519 |
| `deepsets-v1` | 0.720 | 1,236 | 519 |
| `pocketrank-context-v1` | 0.743 | 1,236 | 519 |

The two-parameter cosine-plus-bias baseline beats both learned models on these weak labels. The benchmark mostly rewards embedding proximity, so it says little about whether a fragment would be useful in a song, and with no human evaluation it remains open whether more capacity helps on the real task.

## Grouping

Captured fragments are grouped into projects by feeling and theme. In the
deployed mode (`POCKET_GROUPING_MODE=hybrid`) Gemini makes that call from the
tags, the text and the creator's notes and edits, and is shown the fusion
score as a hint of how alike two recordings sound. Whether its choice
matches what the fusion rule alone would pick is recorded for each fragment,
as a description of how often they agree. With `llm`, the value when the
variable is unset, Gemini decides without the scores. None of this has been
checked against how anyone groups their own work.

The fusion score answers a narrower question, whether two recordings sound
alike; its weights were trained on loops filed in the same sample pack. In
the `fusion` mode, which is not deployed, those weights decide on their own
(`backend/ranking/grouping.py`) and Gemini only writes the narrative, project
title and next action. That mode's threshold, 15.31, is the smallest score at
which same-pack precision reaches 0.50 on the 484 training packs. On the 121
held-out packs it gives precision 0.937 [0.822, 0.995] and recall 0.325
[0.221, 0.480], and fusion's average precision is 0.127 [0.039, 0.206] above
plain MS-CLAP cosine (`research/results-grouping-threshold-v1.md`). Precision
at a fixed threshold depends on library size, and online tags, tempo and key
come from the product's own analysis, so these numbers will not carry over
exactly to a user's library.

## Limitations

- **No weights change online**: with `POCKET_EDIT_CONTEXT=1` (on in the deployment), the language model is shown a summary of the user's own edits (tags added or removed, titles replaced, suggestions completed or skipped) when it writes tags, titles, suggestions and grouping decisions. That shapes the prompt; nothing is trained. The behavioural guardrail (`research/compat_tests/guardrail.py`) only covers learned ranking weights, so it does not apply here, and the effect of the edit summary has not been evaluated. Refitting ranking weights from logged decisions is an offline step that has to pass the guardrail.
- **Session representation limits**: the existing fusion uses pooled region audio and metadata. The selectable `beat-fit-v1` ranker adds approximate timeline placement and chroma/onset structure; it does not reproduce offsets, loops, mixing or effects of real DAW playback.
- **Intent in the fusion rankers**: `fusion-5sig-v1` is affected by the typed intent only through a BPM or key parsed from it when the session lacks one; role words such as "replace the drums" or "add a synth hook" do not change its ranking. `beat-fit-v1` reads only the precomputed `session_beats` and not the parsed intent. `rules-v1` and the text and audio cosine rankers do read role words.
- **No human evaluation**: every reported result uses proxy labels (pack co-membership, controlled perturbations); none measures whether musicians prefer the suggestions. Sample sizes are reported with each result.
- **Backbone audit incomplete**: LAION-CLAP music training data provenance has not been fully verified for commercial deployment.

## Ethical Considerations

- The system ranks only within a user's own library; it never surfaces other users' content.
- No creativity claims: short-term retrieval experiments cannot support assertions about enhancing creativity (per ICCC 2018 evaluation guidelines).
- Audio from user sessions is CLAP-encoded for ranking only. The application does not save the raw session audio or send it to third parties; it decodes the upload in memory, though the web framework may spool a large upload to a temporary file while parsing the request.
- Feedback data is exported for analysis with `backend/scripts/export_feedback.py`, which fetches and writes only allowlisted fields and replaces user IDs with a salted one-way hash. The raw collections hold user IDs and are not dumped. Exports stay on the author's machine.

## Intended Use

Session-conditioned fragment retrieval during live music production in Audiotool. Not intended for general music recommendation, playlist generation, or use outside the Pocket Producer application context.

## Contact

Chuling Li, chuling.li.cs@gmail.com
