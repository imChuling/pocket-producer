# Pocket Producer

> **A session-aware retrieval instrument for unfinished music.** It reads the
> Audiotool project you have open, ranks your own audio fragments by whether
> they *could grow into a piece of music* with what's already there, and
> lets you preview, insert, and undo.

Not a generator. Not a collaborator. A tool you steer.

**Try it:** [pocketproducer.vercel.app/audiotool](https://pocketproducer.vercel.app/audiotool)
(sign in, connect your Audiotool account, open a project, and go)

<!-- **Demo video:** [YouTube link -- fill in after upload] -->

Built for [Audiotool Let's Build 2026](https://www.audiotool.com/LetsBuild/)
with a companion
[ISMIR 2026 Late-Breaking/Demo](https://ismir2026.ismir.net/call-for-late-breaking-demo)
paper.

### What it does

1. **Reads** your open Audiotool session through the Nexus SDK: tempo, track
   roles, playhead position
2. **Ranks** your own fragment library by session compatibility, not just audio
   similarity
3. **Shows evidence** for every suggestion ("121 BPM close to project's 120",
   "adds a role this session doesn't have yet")
4. **Inserts** the chosen fragment at the playhead in one Nexus transaction
5. **Undoes** cleanly: restores the exact prior entity set

Every recommendation is inspectable and reversible. The default ranker is a
hand-tuned rules baseline; a learned five-signal fusion is user-selectable
because the offline evaluation shows its advantage depends on how the
weak-supervision labels are constructed.

---

## The research question

Most music retrieval ranks by **similarity**. But when you re-open a half-finished
project at 1am, the question isn't "what sounds like this," it's:

> **Which of my own fragments could grow into a piece of music with what's already here?**

We call this **session compatibility**: whether a candidate is promising
material for the same piece of music as the fragments already in the open
project (the *session*).
Audio similarity is one observable signal for it, but does not define it; a
fragment that fills a missing role can belong better than one that blends in
perfectly. Direct labels for this target
do not exist at cold start, so the repo trains on a proxy (pack co-membership)
and interrogates its reliability rather than assuming it, including when the
answer is *no*.

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
  → compatibility ranking    rules → linear → DeepSets → 401K attention reranker
  → three grounded suggestions
  → preview · insert at playhead · exact undo
  → preference feedback      (research signal, propensity-aware)
```

Every recommendation shows **structured evidence** ("121 BPM is close to the
project's 120 BPM", "adds a role this session doesn't have yet") drawn from the
ranker's own features -- never generated prose.

---

## Findings (ISMIR 2026 LBD -- all numbers from versioned artifacts)

The paper's evaluation runs on the **pack-only FSLD corpus**: 1,797 loops in
605 true Freesound packs, one pack = one *source*, with a frozen 121-source
held-out split (seed 20260810; the split's SHA-256 was committed before any
evaluation touched it). A five-signal linear fusion (mean/max CLAP cosine,
tempo, key, tag Jaccard) is trained with BPR on pack co-membership weak
labels and compared against frozen cosine. Full commands:
[`research/README.md`](research/README.md).

### Dev set: the fusion advantage disappears under clean labels

Mean over 5 source-grouped splits
([`artifacts/fusion-packonly/fusion.json`](artifacts/fusion-packonly/fusion.json)):

| | overall | hard_similar |
|---|---:|---:|
| frozen cosine | **0.929** | **0.8136** |
| five-signal fusion | 0.925 | 0.8133 |

An earlier corpus that also grouped items by uploader showed fusion +4.0 pp
over cosine on hard_similar; restricting to true pack co-membership erases
the gain (−0.03 pp). Label construction, not the ranker, produced the
apparent advantage.

### Held-out: the delta depends on the configuration

Fusion−cosine on the 121 held-out sources, bootstrap 95% CIs over 10,000
source-level resamples, mean over 5 seeds -- treated as **exploratory** after
a corrected training protocol
([`artifacts/heldout-eval-correction/`](artifacts/heldout-eval-correction/sensitivity.json),
[`artifacts/msclap-sensitivity-correction/`](artifacts/msclap-sensitivity-correction/sensitivity.json)):

| Negative regime | LAION-CLAP | MS-CLAP, source-weighted BPR |
|---|---:|---:|
| hard_similar | +2.1 pp [−1.0, +5.3] | +9.9 pp [+4.4, +15.4] |
| overall | +0.6 pp [−0.4, +1.6] | +2.6 pp [+1.0, +4.2] |

The same split, the same signals -- and a 7.8 pp swing on hard_similar from
embedding and training choices alone.

### Why this shapes the product

Conclusions drawn from the cold-start proxy shift with label, regime, and
representation choices. So the deployed system treats ranking scores as
**proposals, not judgments**: the rules baseline is the default ranker, the
fusion is selectable, every candidate carries per-signal evidence, and every
insertion is a single reversible transaction. The fusion is a cold-start
first-pass filter, not a final decision-maker.

---

## Evaluation setup

- **Preregistered before looking at results** -- [`research/protocol.md`](research/protocol.md)
  (frozen 2026-07-30): primary metric, baselines, splits, and the failure
  criterion are fixed in advance.
- **Metrics must match label semantics** -- asking for nDCG on pairwise labels
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
  entity set -- verified against offline Nexus documents running the official
  WASM validator.
- **Your Audiotool login never leaves the browser.** OAuth tokens live inside
  the Nexus client; the backend never receives them, and a test asserts no token
  material reaches logs or the database.
- **Degrades honestly.** Any ranker failure falls back to the deterministic
  rules baseline with `fallback_used: true` surfaced in the UI. The loop works
  with no model service at all.
- **Missing data is masked, never imputed.** Audiotool documents carry no key
  signature, so the session summary reports "not available" rather than guessing.
- **Every vector carries lineage** -- model id, immutable weight revision
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

Foundation encoders are **frozen and never on the click path** -- embeddings are
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
> `project:write` scope -- and open the dev server at that same origin, since the
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
and suggests a next action -- backed by ~5,970 lines of Apache-2.0 domain skills
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

- **Nexus integration** -- browser OAuth lifecycle, deterministic session
  fingerprinting from document entities, transactional insert with an exact-undo
  receipt, tested against the official offline document validator
- **Retrieval and ranking** -- versioned representation contract with model
  lineage, RRF fusion, six comparison methods, a capacity ladder with a hard
  parameter budget enforced by unit test
- **Research design** -- preregistered protocol, label-compatible metrics
  enforced in code, per-item license manifest for the pretraining corpus, blind
  pairwise annotation flow, anonymized export
- **The evidence audit** -- including deciding which of my own earlier claims to
  delete
- **Full stack** -- FastAPI backend, Next.js frontend, Cloud Run + Vercel deploy

---

## License

[Apache 2.0](LICENSE), including all domain skills.
