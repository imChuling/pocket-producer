# Pocket Producer

> **A session-aware retrieval instrument for unfinished music.** It reads the
> Audiotool project you have open, ranks your own audio fragments by how useful
> they are for your *next* move — and lets you preview, insert, and undo.

Not a generator. Not a collaborator. A tool you steer.

**Status (2026-08-01):** research prototype under active development for
[Audiotool Let's Build 2026](https://www.audiotool.com/LetsBuild/) and an
[ISMIR 2026 Late-Breaking/Demo](https://ismir2026.ismir.net/call-for-late-breaking-demo)
submission. Nexus read/write is implemented and offline-tested against the
official SDK's document validator; real-account screen capture is pending.

---

## The research question

Most music retrieval ranks by **similarity**. But when you re-open a half-finished
project at 1am, the question isn't "what sounds like this" — it's:

> **Which of my own fragments is worth trying next?**

We call this **continuation utility**, and it is deliberately not the same
objective as acoustic similarity. A fragment that fills a missing role can be
more useful than one that blends in perfectly. Whether a model can learn this
distinction — and whether it beats simple baselines — is an empirical question
this repo is set up to answer honestly, including when the answer is *no*.

`utility` is a named metric in the co-creative systems evaluation literature
(Karimi et al., ICCC 2018), which also observes that most co-creative systems
evaluate user experience rather than the usefulness of what the system
contributes. That gap is what the evaluation protocol here targets.

---

## The loop

```text
Audiotool project (live, via Nexus SDK)
  → session fingerprint      tempo · track roles · playhead · your stated intent
  → retrieval                per-representation-space search, fused by RRF
  → continuation ranking     rules → linear → DeepSets → 401K attention reranker
  → three grounded suggestions
  → preview · insert at playhead · exact undo
  → preference feedback      (research signal, propensity-aware)
```

Every recommendation shows **structured evidence** ("121 BPM is close to the
project's 120 BPM", "adds a role this session doesn't have yet") drawn from the
ranker's own features — never generated prose.

---

## Preliminary findings (all numbers from versioned artifacts)

### Backbone bake-off — [`artifacts/backbone-bakeoff.json`](artifacts/backbone-bakeoff.json)

Frozen audio-text backbones compared on 2,558 licensed FSLD loops:

| Backbone | Same-source Recall@10 | Genre zero-shot | Role zero-shot | Vector size |
|---|---:|---:|---:|---:|
| MS-CLAP 2023 | 0.692 | 0.384 | 0.533 | 4 KB |
| LAION-CLAP music | **0.713** | **0.415** | **0.556** | **2 KB** |

LAION-CLAP wins every probe at half the storage — but its training-data
provenance audit is not complete, so **MS-CLAP remains the deployment default**.
Representation quality and deployment eligibility are separate decisions.

### Capacity ladder — [`artifacts/model-capacity.json`](artifacts/model-capacity.json)

| Rung | Trainable params | CPU p95 (batch 32 × 32 tokens) |
|---|---:|---:|
| `linear-v1` | 20 | 0.7 ms |
| `deepsets-v1` | 297,729 | 1.3 ms |
| `pocketrank-context-v1` | **401,025** (hard gate: < 500K) | 5.3 ms |

### An honest negative result

On **weak** supervision (1,755 leave-one-out pairs from same-pack FSLD loops,
split by source):

| | MS-CLAP space | LAION space |
|---|---:|---:|
| `linear-v1` (20 params) | **0.880** | **0.897** |
| `pocketrank-context-v1` (401K params) | 0.743 | 0.762 |

**The 20-parameter model wins.** This is not a bug — it is the point. Weak
labels define "positive" as *came from the same pack*, and same-pack loops are
already close in CLAP space, so cosine similarity is near-optimal **for that
proxy task**. It is direct evidence that *similar ≠ useful*, and that the
research question can only be settled with human judgments of continuation
utility — which is exactly what the annotation protocol collects.

Per the preregistered gate, the contest build therefore ships `rules-v1` /
`audio-cosine-v1`, not the learned reranker.

---

## Evaluation setup

- **Preregistered before looking at results** — [`research/protocol.md`](research/protocol.md)
  (frozen 2026-07-30): primary metric, baselines, splits, and the failure
  criterion are fixed in advance.
- **Metrics must match label semantics** — asking for nDCG on pairwise labels
  raises `MetricEligibilityError`; the rule is enforced in code, not by discipline
  ([`backend/ranking/metrics.py`](backend/ranking/metrics.py)).
- **Six comparison methods**: recency · text-only (Voyage) · audio-cosine (CLAP) ·
  mean-session · rules · context reranker.
- **Grouped splits** by participant and by source pack; no time-stretched or
  duplicate audio crosses a split boundary.
- **Honest skips**: a model that cannot legitimately score an example is
  recorded as skipped, never given a silent zero.

### Licensed pretraining corpus

The Freesound Loop Dataset is **not** uniformly licensed. All 9,493 loops were
classified per item ([`research/build_fsld_manifest.py`](research/build_fsld_manifest.py)):

| CC-BY | CC0 | CC-BY-NC | Sampling+ | Unknown |
|---:|---:|---:|---:|---:|
| 4,827 | 3,230 | 1,215 | 221 | 0 |

Research use covers all 9,493; only the 8,057 CC0/CC-BY items are eligible for
redistribution, and NC items never enter commercial paths. See
[DATA_CREDITS.md](DATA_CREDITS.md).

---

## Responsible design

- **Reversible by construction.** Insertion uploads the sample, waits for server
  acknowledgement, then modifies the document in a *single* Nexus transaction.
  The receipt records every created entity, so undo restores the exact prior
  entity set — verified against offline Nexus documents running the official
  WASM validator.
- **Your Audiotool login never leaves the browser.** OAuth tokens live inside
  the Nexus client; the backend never receives them, and a test asserts no token
  material reaches logs or the database.
- **Degrades honestly.** Any ranker failure falls back to the deterministic
  rules baseline with `fallback_used: true` surfaced in the UI. The loop works
  with no model service at all.
- **Missing data is masked, never imputed.** Audiotool documents carry no key
  signature, so the session summary reports "not available" rather than guessing.
- **Every vector carries lineage** — model id, immutable weight revision
  (sha256 of the checkpoint), input audio hash, dims, pooling.
- **No claims of increased creativity.** Short studies cannot support that;
  we measure perceived relevance and perceived control instead.

---

## Architecture

```text
Browser                          Backend (FastAPI)              Offline
─────────                        ─────────────────              ───────
Nexus SDK  ──documents──▶  session fingerprint
   │                              │
   │                       retrieval (exact cosine)      CLAP embedding worker
   │                              │  + RRF fusion         (frozen, cached by
   │                              ▼                        audio sha256)
   │                       ranker registry ──────────▶  capacity ladder
   │                              │  (rules fallback)     artifacts + model card
   ◀──── three suggestions ───────┘
   │
   └── preview / insert / undo ──▶ feedback log (exposure + rank position)
```

Foundation encoders are **frozen and never on the click path** — embeddings are
computed offline and cached; the online ranker is a sub-500K CPU model.

See [ARCHITECTURE.md](ARCHITECTURE.md) and
[`docs/research/2026-07-25-pocketrank-frontier-architecture.md`](docs/research/2026-07-25-pocketrank-frontier-architecture.md).

---

## Run it locally

```bash
# Backend
cd backend
python -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # fill in credentials
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -q
./.venv/bin/uvicorn api.main:app --reload --port 8000
```

```bash
# Frontend
cd frontend
npm install
echo "NEXT_PUBLIC_AUDIOTOOL_CLIENT_ID=your-client-id" >> .env.local
npm run check                 # eslint + tsc + vitest
npm run dev                   # → http://127.0.0.1:3000/audiotool
```

> **Use `127.0.0.1`, not `localhost`.** Audiotool rejects `localhost` in an
> application's redirect URIs, so register `http://127.0.0.1:3000` on the
> [developer dashboard](https://developer.audiotool.com/applications) with the
> `project:write` scope — and open the dev server at that same origin, since the
> popup OAuth flow validates `window.location.origin` against it. If Firebase
> then reports `auth/unauthorized-domain`, add `127.0.0.1` under
> Authentication → Settings → Authorized domains.

Reproduce the research artifacts:

```bash
python research/build_fsld_manifest.py                    # per-item licenses
python research/embed_fsld_subset.py --adapter msclap-2023
python research/benchmark_backbones.py --items msclap-2023=research/data/fsld/items.jsonl
python research/build_weak_pairs.py --items-file research/data/fsld/items.jsonl
python research/train_context_ranker.py --weak-data research/data/weak_pairs.jsonl
python research/evaluate.py --dataset research/data/heldout.jsonl
```

Every artifact carries a dataset hash and the commit that produced it.

---

## Tech stack

| Layer | Choice |
|---|---|
| DAW integration | [`@audiotool/nexus`](https://developer.audiotool.com/js-package-documentation/) 0.0.17 (exact pin) |
| Audio representations | MS-CLAP 2023 (default) · LAION-CLAP music (challenger), both frozen |
| Text representation | Voyage `voyage-3` (legacy fragments, kept as a baseline) |
| Ranking | PyTorch, exported to safetensors; ONNX targeted for serving |
| Backend | FastAPI · MongoDB Atlas · Firebase Auth · Google Cloud Storage |
| Frontend | Next.js 16 · React 19 · Tailwind v4 · Vitest |
| License | Apache 2.0 |

---

## What came before

Pocket Producer began as an **agentic creative-memory system** (Google Cloud
Rapid Agent Hackathon, June 2026): capture a fragment, and a Gemini-powered
Producer/Memory agent pair groups it into projects, classifies relationships,
and suggests a next action — backed by ~5,970 lines of Apache-2.0 domain skills
loaded through progressive disclosure ([SKILLS.md](SKILLS.md)).

That system still runs the capture and library side, and its
[demo video](https://youtu.be/yZbZ7jUQ_0A) documents it.

The current work is a deliberate change of direction after an evidence audit
found the ranking layer could not support its own claims: a single `embedding`
field mixed modalities, "similarity" was standing in for usefulness, and there
was no held-out evaluation. The audit
([`docs/superpowers/plans/2026-07-25-pocketrank-evidence-audit.md`](docs/superpowers/plans/2026-07-25-pocketrank-evidence-audit.md))
graded 75 claims by evidence strength and deleted the ones that could not be
supported. Everything above is what replaced them.

---

## My contribution

Single author. Across both phases:

- **Nexus integration** — browser OAuth lifecycle, deterministic session
  fingerprinting from document entities, transactional insert with an exact-undo
  receipt, tested against the official offline document validator
- **Retrieval and ranking** — versioned representation contract with model
  lineage, RRF fusion, six comparison methods, a capacity ladder with a hard
  parameter budget enforced by unit test
- **Research design** — preregistered protocol, label-compatible metrics
  enforced in code, per-item license manifest for the pretraining corpus, blind
  pairwise annotation flow, anonymized export
- **The evidence audit** — including deciding which of my own earlier claims to
  delete
- **Full stack** — FastAPI backend, Next.js frontend, Cloud Run + Vercel deploy

---

## License

[Apache 2.0](LICENSE), including all domain skills.
