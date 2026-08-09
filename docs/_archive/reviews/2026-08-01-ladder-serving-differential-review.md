# Pocket Producer ladder-serving differential review

Date: 2026-08-01  
Branch / baseline: `dev-v1` at `4b8db22` plus the current working-tree diff  
Scope: learned ladder checkpoint export, online adapter registration, Audiotool model selector, research and submission artifacts

## Verdict

**Changes requested before committing the serving path or freezing the ISMIR PDF.**

The capacity-ladder result is genuinely reproducible: an independent rerun with the recorded FSLD weak-pair file, seed `20260725`, 15 epochs, and learning rate `0.001` reproduced all 14 output files byte-for-byte. The observed validation accuracies are `0.8795` (linear), `0.7203` (DeepSets), and `0.7425` (PocketRank-Context).

The current online path and paper evidence chain nevertheless contain merge/submission blockers. The most important are an empty-success response that bypasses the promised rules fallback, a human-evaluation pipeline that cannot yet score the learned models, and inconsistent parameter counts between the served checkpoints and the manuscript.

## Findings

### [HIGH] Learned adapters can return zero recommendations without fallback

**Location:** `backend/ranking/ladder_adapter.py:74-89`

Candidates without a stored audio embedding are skipped. If all candidates are unscorable, the adapter returns `fallback_used=false` and an empty list instead of raising `InsufficientContextError`. The service therefore never invokes `rules-v1`. This was reproduced directly with the real `pocketrank-context-v1` checkpoint: a valid 1024-dimensional session context plus one candidate without an audio embedding returned a successful response containing no candidates.

This violates the manuscript's statement that unavailable learned ranking falls back to rules and creates a high-risk demo failure. Raise the same insufficiency exception used for missing session context, or make `RankingService` treat an empty learned response as insufficient. Add tests for zero, partial, wrong-dimensional, and non-finite embeddings.

### [HIGH] The preregistered primary comparison cannot yet be computed

**Location:** `backend/ranking/offline_eval.py:80-92`, `research/evaluate.py:26-44`

The evaluation registry supports only `rules-v1`, `recency-v1`, `text-only-v1`, `audio-cosine-v1`, and `mean-session-v1`. Passing `linear-v1`, `deepsets-v1`, or `pocketrank-context-v1` raises `ValueError`. Consequently, labels collected through `/annotate` cannot currently answer the preregistered hypothesis that PocketRank-Context improves over the strongest simpler baseline.

Before spending scarce time on annotation, add checkpoint-backed scorers to the fixed offline evaluator and a smoke fixture that exercises all declared comparison models. Human labels should remain held out from training for the primary evaluation; any fine-tuning set must be participant/project-separated from that test set.

### [HIGH] Manuscript numbers describe a different configuration from the trained/served checkpoints

**Location:** `docs/ismir2026/assets/capacity-table.tex:5-7`, `docs/ismir2026/lbd.tex:199`, `research/train_context_ranker.py:62-65`

FSLD training explicitly sets `structured_dim=0`, producing 2 / 295,425 / 400,449 parameters. The manuscript's capacity table reports 20 / 297,729 / 401,025 and the prose says “20-parameter linear,” which comes from the default 18-feature capacity harness rather than the submitted checkpoint.

Regenerate capacity/latency assets from the exact checkpoint configs or clearly label the table as an untrained full-feature architecture. For the current weak-label result and serving artifact, “2-parameter cosine-plus-bias baseline” is the accurate statement.

### [HIGH] The negative-result interpretation overclaims what the weak-label experiment establishes

**Location:** `docs/ismir2026/lbd.tex:199-208`, `docs/ismir2026/lbd.tex:231-234`

The experiment establishes that a two-parameter cosine model predicts same-pack weak labels better than the larger challengers. Without human continuation labels, it does not “confirm that same-pack co-occurrence does not measure continuation utility.” A defensible interpretation is that the benchmark predominantly rewards embedding proximity and therefore cannot establish validity for continuation utility. Human evaluation is required to test that validity.

### [MEDIUM] Model selector advertises unavailable models and lacks serving-status evidence

**Location:** `frontend/src/components/audiotool/continuation-panel.tsx:40-48`, `backend/ranking/service.py:80-94`

The frontend hard-codes seven choices even though audio and ladder adapters are conditional on server environment and checkpoint availability. Selecting an absent model silently resolves to rules. The existing `/model-card` endpoint already exposes the registered set; the selector should be populated from it, with a compact served-model/fallback label suitable for the demo. Add a component test proving the selected model ID is sent and an API/E2E test proving the served model ID matches the loaded checkpoint.

### [MEDIUM] Artifact bundle contains duplication and a stale smoke report

**Location:** `research/train_context_ranker.py:98-110`, `artifacts/evaluation-smoke.json:1-85`

The trainer writes PocketRank-Context both at the artifact root and under `pocketrank-context-v1/`; the two `model.safetensors` files have the same SHA-256 (`13e14ab...`). The full artifact directory is about 4.2 MB because of this duplication. Choose one canonical layout and make both serving and rendering consume it.

`evaluation-smoke.json` contains two synthetic examples, excludes every learned ladder model, and records commit `f437166...`, which is not an object in this repository. It is useful only as a CI fixture. Do not present it as research evidence; regenerate it against the intended commit after learned scorers exist, or omit it from this feature commit.

### [MEDIUM] Current green-test summary overstates coverage

Fresh verification produced:

- Frontend: `tsc --noEmit` passed; 46/46 Vitest tests passed.
- Frontend full check: failed on five pre-existing ESLint errors and six warnings.
- Backend full discovery: 191 passed, 1 skipped, 2 failed, 3 setup errors.
- Ranking plus ranking-route set, excluding the Firebase credential-dependent invalid-token test: 158 passed, 1 skipped.

The new `LadderRankerAdapter`, `POCKET_LADDER_DIR` registration, and model-selection interaction have no dedicated tests. The unrelated failures should be recorded separately, but they cannot be summarized as only two failures: pytest also collects three script-style functions with missing fixtures.

### [MEDIUM] Human-study wording and recruitment path need evidence

**Location:** `docs/ismir2026/lbd.tex:211-223`, `research/generate_annotation_pairs.py:36-59`

The repository contains no real exported pilot artifact, while the manuscript says pilot collection has begun. In addition, task generation and fragment lookup are scoped to each authenticated user's own embedded library. A 6–8 participant study therefore requires each participant to have enough multi-project material, or an explicit consented shared stimulus set. Twenty labels from the author are a pilot, not a 6–8 participant study.

Until a real label/export exists, change the manuscript to “pilot data collection is prepared/planned.” Record consent, exclusion rules, pilot status, and whether author labels are excluded from the evaluation set.

### [LOW] Model-card endpoint leaks deployment paths and omits provenance

**Location:** `backend/ranking/ladder_adapter.py:49-54`

The public model card uses the server filesystem checkpoint path as metadata while omitting the checkpoint hash, dataset hash, dimensions, parameter count, and label layer already available in artifact files. Return research provenance rather than an absolute path.

## Submission and repository decisions

1. **Do not commit the current serving bundle unchanged.** Fix the empty fallback, add adapter/selector/E2E coverage, and reconcile the checkpoint layout first.
2. **Do not commit `research/data/fsld/items_laion-clap-music.jsonl`.** Add it to `research/data/fsld/.gitignore`; retain a manifest, generation command, source/license note, and content hash.
3. **Keep planning documents out of the feature commit.** If they are intended as public portfolio process artifacts, review them for stale claims and add them in a separate docs commit. Otherwise keep them private; unchecked sprint notes weaken a polished repository.
4. **The three-page LBD PDF is structurally compliant if page 3 contains only references plus acknowledgements/AI usage.** Current page 3 does. Do not spend time forcing the whole PDF to two pages; spend that time on claim consistency and reference verification.
5. **References are a hard submission blocker.** There are 11 bibliography entries marked pending (the twelfth `PENDING` match is the status legend), and the compiled PDF visibly includes an “author list must be verified” note.

## Recommended merge gates

- No empty learned response when rules can rank candidates.
- Runtime model list drives the selector; selected and served IDs are observable.
- Real checkpoint E2E request for all three ladder models, including fallback cases.
- Offline evaluator scores every model in the preregistered comparison set.
- Capacity table, weak-results prose, model cards, and checkpoint configs agree exactly.
- All bibliography entries verified against primary sources and placeholder notes removed.
- One real pilot export before claiming collection has begun.
- Deployed demo URL verified from a clean browser session before Let's Build capture.

