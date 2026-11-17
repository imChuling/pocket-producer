# Model Card: Pocket Producer Ranking System

## Local submission revision, 2026-11-16

The capacity-ladder descriptions below document earlier research models;
they do not establish that every model is deployed or preference-validated.
The product default remains `rules-v1`; the shipped fusion scores five
signals. `beat-fit-v1` is registered and deployed as a selectable ranker;
the production frame backfill has not run, so fragments ingested before it
are left out of its lists. Offline feedback training is not automatic online
adaptation. Seven-signal artifacts are explicitly research-only and rejected
by the online five-signal loader. See [capability boundaries and evidence
semantics](research/design-online-signals.md) and the [project note](docs/portfolio/PROJECT_NOTE.md).

Controlled perturbation and as-is synchronized-stem retrieval results do
not establish musician preference or improved creativity. The two-signal
chroma/onset choice has no demonstrated incremental retrieval benefit over
onset alone. COCOLA_HP_v1's official training sets are MoisesDB, Slakh2100
and CocoChorales; the older MUSDB18-HQ assertion is corrected in the dated
protocol errata. No independent training-file reconstruction excludes overlap.

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

Nine rankers are registered in the default deployment (with `POCKET_ENABLE_CLAP=1` and the fusion weights present, as deployed): `rules-v1`, `recency-v1`, `mean-session-v1`, `text-only-v1`, `audio-cosine-v1`, `role-gap-v1`, `harmonic-fit-v1`, `beat-fit-v1` and `fusion-5sig-v1`. The eight without fitted weights are listed here; `fusion-5sig-v1`, whose five weights were fitted on pack co-membership, is covered under Grouping use and Limitations.

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

### Human labels (history; none in the current results)

A blind A/B annotation interface (dev builds only) and a pairwise annotation protocol were built early on, with a planned rule that a learned model would need to beat the cosine baseline on human pairwise accuracy before deployment. An early small signal-alignment analysis was later withdrawn because its raw vote matrix is no longer available, and the author then decided not to run human studies, so that rule no longer applies. A single-rater listening protocol (`research/prereg_human_v1.md`) was committed to the repository but not run.

The only check now wired into code is narrower: when fusion weights are refit from logged feedback, the new weights must pass the behavioural guardrail (`research/compat_tests/guardrail.py`), or `research/finetune_from_feedback.py` writes no weights. It covers that one flow only, not other models or deployment paths, and it does not stand in for human preference data.

## Evaluation

- **Metric**: pairwise accuracy (fraction of pairs where the model ranks the preferred candidate higher). All results below use weak labels; no human pairwise labels are in them.
- **Grouping**: the harness can group by participant so one prolific annotator would not dominate; this is unused while there are no human labels
- **Label-type enforcement**: code raises `ValueError` if labels are not `pairwise`
- **Honest skips**: models that cannot score an example (missing embeddings, no session context) skip it; skips are counted, not zeroed

### Weak-label results (FSLD, val split)

| Model | Val Pairwise Accuracy | Train Examples | Val Examples |
|---|--:|--:|--:|
| `linear-v1` | **0.880** | 1,236 | 519 |
| `deepsets-v1` | 0.720 | 1,236 | 519 |
| `pocketrank-context-v1` | 0.743 | 1,236 | 519 |

**Key finding**: the two-parameter cosine-plus-bias baseline beats both learned models on weak labels. The benchmark predominantly rewards embedding proximity, so it cannot establish validity for continuation utility. A single-rater listening protocol was designed (`research/prereg_human_v1.md`) and, by the author's choice, not run, so whether learned capacity helps on the real task remains open.

## Grouping use (behind a flag)

With `POCKET_GROUPING_MODE=fusion` (default `llm`), the same
`fusion-5sig-v1` weights decide which project a new fragment joins, scored
pair by pair (`backend/ranking/grouping.py`). The weights were trained on
pack co-membership, which asks the same question as grouping, but on pack
data. The threshold, 15.31, is the smallest score at which same-pack
precision reaches 0.50 on the 484 training packs; on the 121 held-out packs
it gives precision 0.937 [0.822, 0.995] and recall 0.325 [0.221, 0.480],
and fusion's average precision exceeds plain MS-CLAP cosine by 0.127
[0.039, 0.206] (`research/results-grouping-threshold-v1.md`). Precision at a
fixed threshold depends on library size, and online tags, tempo and key come
from the product's own analysis, so these numbers do not transfer directly
to a user's library. Neither the threshold nor the decision has been
checked against any musician's own grouping. Gemini still writes the
narrative, project title and next action; it does not make the decision.
With `POCKET_GROUPING_MODE=hybrid`, Gemini makes the decision and is shown
the fusion scores and what the fusion rule would choose; whether the two
agree is recorded per fragment, and that agreement rate is the measure of
how much the score weighs in. With `llm`, the value when the variable is unset, grouping is decided
by the Gemini agents alone. The deployment sets `hybrid`.

## Limitations

- **No online weight adaptation; edit context is prompt conditioning**: no ranking or grouping weights adapt online. With `POCKET_EDIT_CONTEXT=1` (off when unset, on in the deployment), the language model is shown a summary of the user's own edits (tags added or removed, titles replaced, suggestions completed or skipped) when it writes tags, titles, suggestions and grouping decisions. This is in-context conditioning, not training. It is not covered by the behavioural guardrail (`research/compat_tests/guardrail.py`), which gates learned ranking weights only, and its effect has not been evaluated. Refitting weights from logged decisions remains an offline step that must pass that guardrail.
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

Chuling Li — chuling.li.cs@gmail.com
