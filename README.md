# Pocket Producer

[![ISMIR 2026 LBD](https://img.shields.io/badge/ISMIR%202026-Late--Breaking%20Demo-a0b5eb?style=flat&labelColor=1a1a2e)](https://ismir2026.ismir.net/)
[![Code: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-cfdaf5?style=flat&labelColor=1a1a2e)](LICENSE)
[![Paper: CC BY-NC 4.0](https://img.shields.io/badge/Paper-CC%20BY--NC%204.0-ff9473?style=flat&labelColor=1a1a2e)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Try it](https://img.shields.io/badge/Try%20it-pocketproducer.vercel.app-ffa773?style=flat&labelColor=1a1a2e)](https://pocketproducer.vercel.app)

> **A session-aware retrieval instrument for unfinished music.** It reads the
> Audiotool project you have open, ranks your own audio fragments by whether
> they *could grow into a piece of music* with what's already there, and
> lets you preview, insert, and undo.

You stay in charge. It just retrieves.

**Try it:** [pocketproducer.vercel.app](https://pocketproducer.vercel.app)
**Audiotool integration:** [pocketproducer.vercel.app/audiotool](https://pocketproducer.vercel.app/audiotool)

**Demo video:** [youtu.be/s56Rp_1M9OE](https://youtu.be/s56Rp_1M9OE)

Built for [Audiotool Let's Build 2026](https://www.audiotool.com/LetsBuild/).
Accepted as a Late-Breaking Demo at [ISMIR 2026](https://ismir2026.ismir.net/):
*Pocket Producer: Session-Conditioned Retrieval as User-Controlled Proposal*
(see [CITATION.cff](CITATION.cff)).
Ranking evaluation on the Freesound Loop Dataset in `research/`.

### What it does

1. **Reads** your open Audiotool session through the Nexus SDK: tempo, track
   roles, the samples already on the timeline
2. **Ranks** your own fragment library by session compatibility (tempo, role
   gaps, intent overlap), beyond plain audio similarity
3. **Shows evidence** for every suggestion ("121 BPM close to project's 120",
   "adds a role this session doesn't have yet")
4. **Inserts** the chosen fragment at the start of the timeline in one Nexus
   transaction (the SDK does not expose the playhead)
5. **Undoes** cleanly: restores the exact prior entity set
6. **Imports** an existing Audiotool project's samples into your library in
   one click, so your own back catalog becomes searchable creative memory

Every recommendation is inspectable and reversible. The default ranker is a
hand-tuned rules baseline; a learned five-signal fusion is user-selectable
because the offline evaluation shows its advantage depends on how the
weak-supervision labels are constructed.

### Nexus SDK integration

Full read-write cycle against live Audiotool documents.

- **Session fingerprinting.** Walks the document entity tree to pull out
  tempo, track types, region samples. No manual input needed.
- **Transactional insert.** Uploads the sample, waits for the server to
  confirm, then writes the region in a single `document.modify` call.
  The document stays consistent even if the network drops mid-flow.
- **Exact undo.** The insert receipt records every entity ID that was
  created. Undo removes exactly those, validated against the official
  Nexus WASM document validator.
- **One-click import.** Pulls an existing project's samples through the
  Nexus download API and feeds them into the fragment library. Old
  projects become material for new ones.
- **SDK bug patch shipped in-repo.** We hit a production crash where
  `insertSample` fails in any minified build (all protobuf class names
  collapse to `class e`). One-line fix: compare `typeName` instead of
  constructor `.name`. Patch in `frontend/patches/`, root-cause write-up
  in `docs/nexus-bug-report.md`.

---

## The research question

Most music retrieval ranks by **similarity**. When you re-open a half-finished
project at 1am, the question is different:

> **Which of my own fragments could grow into a piece of music with what's already here?**

We call this **session compatibility**: whether a candidate is promising
material for the same piece of music as the fragments already in the open
project (the *session*).
Audio similarity is one signal for it, and sometimes a fragment that fills a
missing role belongs better than one that blends in perfectly. Direct labels for this target
do not exist at cold start, so the repo trains on a proxy (pack co-membership)
and interrogates its reliability rather than assuming it, including when the
answer is *no*.

`utility` is a named metric in the co-creative systems evaluation literature
(Karimi et al., ICCC 2018), which also observes that most co-creative systems
evaluate user experience rather than the usefulness of what the system
contributes. That gap is what the evaluation protocol here targets.

---

## The loop

![System overview: the live Audiotool session is fingerprinted, the ranker proposes candidates with per-signal evidence, and the musician previews, inserts, or undoes](docs/system-figure.png)

```text
Audiotool project (live, via Nexus SDK)
  → session fingerprint      tempo · tags of inserted fragments · up to 8 region
                             samples encoded with MS-CLAP (+ chroma) · stated intent
  → five signals φ(s,x)      mean/max CLAP cosine · tempo · key (0 online) · tag Jaccard
  → ranker                   rules-v1 (default, 7 non-audio signals)
                             fusion-5sig-v1 (selectable, w⊤φ trained by BPR)
                             + mean-session · audio-cosine · role-gap · harmonic-fit
  → proposals with evidence  per-signal chips, relative to the served set
  → preview · insert at bar 1 · exact undo
  → exposure + decision log  served signals and accept/reject, the path to
                             replacing the cold-start proxy with real preference
```

Every recommendation shows **structured evidence** ("121 BPM is close to the
project's 120 BPM", "adds a role this session doesn't have yet"), pulled
straight from the ranker's own features. No generated prose.

---

## Findings (all numbers from versioned artifacts)

The evaluation runs on the **pack-only FSLD corpus**: 1,797 loops in
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
source-level resamples, mean over 5 seeds, treated as **exploratory** after
a corrected training protocol
([`artifacts/heldout-eval-correction/`](artifacts/heldout-eval-correction/sensitivity.json),
[`artifacts/msclap-sensitivity-correction/`](artifacts/msclap-sensitivity-correction/sensitivity.json)):

| Negative regime | LAION-CLAP | MS-CLAP, source-weighted BPR |
|---|---:|---:|
| hard_similar | +2.1 pp [−1.0, +5.3] | +9.9 pp [+4.4, +15.4] |
| overall | +0.6 pp [−0.4, +1.6] | +2.6 pp [+1.0, +4.2] |

Same split, same signals, and a 7.8 pp swing on hard_similar from
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

- **Preregistered before looking at results.** [`research/protocol-v2.md`](research/protocol-v2.md)
  (frozen 2026-07-30): primary metric, baselines, splits, and the failure
  criterion are fixed in advance.
- **Metrics must match label semantics.** Asking for nDCG on pairwise labels
  raises `MetricEligibilityError`; the rule is enforced in code, not by discipline
  ([`backend/ranking/research/metrics.py`](backend/ranking/research/metrics.py)).
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
  entity set, verified against offline Nexus documents running the official
  WASM validator.
- **Your Audiotool login never leaves the browser.** OAuth tokens live inside
  the Nexus client; the backend never receives them, and a test asserts no token
  material reaches logs or the database.
- **Degrades honestly.** Any ranker failure falls back to the deterministic
  rules baseline with `fallback_used: true` surfaced in the UI. The loop works
  with no model service at all.
- **Missing data is masked, never imputed.** Audiotool documents carry no key
  signature, so the session summary reports "not available" rather than guessing.
- **Every vector carries lineage.** Model id, immutable weight revision
  (sha256 of the checkpoint), input audio hash, dims, pooling.
- **No claims of increased creativity.** Short studies can't support that.
  We measure perceived relevance and perceived control instead.

---

## Architecture

```text
Browser                          Backend (FastAPI)                   Offline
─────────                        ─────────────────                   ───────
Nexus SDK ──documents──▶ session fingerprint
   │        + region audio ──▶ /session-embed (MS-CLAP + chroma,
   │                           one shared instance, serialized)
   │                              │
   │                       ranker registry ─────────────────▶ FSLD pack co-membership
   │                        rules-v1 (default) ◀── fallback      → LOO pairs → BPR
   │                        fusion-5sig-v1 (w from JSON)          → weights.json
   │                        mean-session · audio-cosine
   │                        role-gap · harmonic-fit
   ◀──── proposals + evidence ────┘
   │
   └── preview / accept / insert / undo ──▶ ranking_requests (served signals)
                                           ranking_feedback (decisions)
                                           → finetune_from_feedback.py
```

Foundation encoders are frozen and never trained online. Candidate vectors
are computed once at ingest and stored with lineage; the online ranker is a
five-weight linear model, so a rank request is a few milliseconds of NumPy.

See [ARCHITECTURE.md](ARCHITECTURE.md).

---

## First run

A fresh account starts with an empty fragment library. The fastest way to
populate it is Audiotool itself: open
[pocketproducer.vercel.app/audiotool](https://pocketproducer.vercel.app/audiotool),
connect your Audiotool account, open any of your projects, and click
**Import samples to library**. Your own samples are downloaded, analyzed,
and become rankable fragments in under a minute — the full
suggest → preview → insert → undo loop is live from there. (Recording or
uploading audio on the Capture page works too.)

---

## Run it locally

```bash
# Backend
cd backend
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt && ./.venv/bin/pip install pytest ruff
cp .env.example .env          # fill in credentials
./.venv/bin/pytest -q && ./.venv/bin/ruff check .
POCKET_ENABLE_CLAP=1 ./.venv/bin/uvicorn api.main:app --reload --port 8080
curl localhost:8080/ready     # mongo, CLAP state, registered rankers
```

`POCKET_ENABLE_CLAP=1` loads MS-CLAP (about 60 s on first start; it is shared
by every ranker). Without it only the non-audio rankers serve. The CLAP stack
is not in `requirements.txt`; install it the way the Dockerfile does:

```bash
./.venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.6,<3" torchaudio
./.venv/bin/pip install "msclap>=1.3,<2"
```

```bash
# Frontend
cd frontend
pnpm install               # pnpm required: applies patches/ to @audiotool/nexus
cp .env.example .env.local     # API URL, Firebase web config, Audiotool client id
pnpm run check                 # eslint + tsc + vitest
pnpm run dev                   # → http://127.0.0.1:3000/audiotool
```

> **Use `127.0.0.1`, not `localhost`.** Audiotool rejects `localhost` in an
> application's redirect URIs, so register `http://127.0.0.1:3000` on the
> [developer dashboard](https://developer.audiotool.com/applications) with the
> `project:write` scope. Open the dev server at that same origin because the
> popup OAuth flow validates `window.location.origin` against it. If Firebase
> then reports `auth/unauthorized-domain`, add `127.0.0.1` under
> Authentication → Settings → Authorized domains.

Deploy the backend (env vars, secrets and scaling are versioned, so a deploy
can never silently drop configuration):

```bash
backend/deploy/deploy.sh            # build + deploy to Cloud Run
backend/deploy/deploy.sh --config   # re-apply configuration only
```

---

## Reproducing the paper

Every number in the ISMIR LBD abstract maps to a versioned JSON under
[`artifacts/`](artifacts/), produced by the scripts in
[`research/`](research/) and cross-checked by
[`research/check_paper_numbers.py`](research/check_paper_numbers.py)
(151 assertions, run in CI). The command for each table and figure is in
[`research/README.md`](research/README.md); the deployed fusion weights
([`artifacts/fusion-deploy/weights.json`](artifacts/fusion-deploy/weights.json))
retrain to within 1e-6 from the frozen split. Follow-up checks that did
not make the paper (standardization, seven signals, key masking, a MERT
representation column, mining negatives in an independent space) are
documented there too, including the ones that came out negative.

Cite with [`CITATION.cff`](CITATION.cff).

---

## Tech stack

| Layer | Choice |
|---|---|
| DAW integration | [`@audiotool/nexus`](https://developer.audiotool.com/js-package-documentation/) 0.0.17 (exact pin) |
| Audio representations | MS-CLAP 2023 (deployed, one shared CPU instance) · LAION-CLAP music and MERT-v1-95M (offline sensitivity columns), all frozen |
| Text representation | Voyage `voyage-3` (legacy fragments, kept as a baseline) |
| Ranking | Five-signal linear fusion in NumPy, BPR-trained offline, weights shipped as JSON; capacity-ladder models (linear, DeepSets, attention) kept as offline challengers |
| Backend | FastAPI · MongoDB Atlas · Firebase Auth · Google Cloud Storage |
| Frontend | Next.js 16 · React 19 · Tailwind v4 · Vitest |
| License | Apache 2.0 |

---

## What came before

Pocket Producer started as an **agentic creative-memory system** (Google Cloud
Rapid Agent Hackathon, June 2026). Capture a fragment, and a Gemini-powered
Producer/Memory agent pair groups it into projects, classifies relationships,
and suggests a next action. ~5,970 lines of Apache-2.0 domain skills loaded
through progressive disclosure ([SKILLS.md](SKILLS.md)).

That system still runs the capture and library side, and its
[demo video](https://youtu.be/yZbZ7jUQ_0A) documents it.

The current work is a deliberate change of direction after an evidence audit
found the ranking layer could not support its own claims: a single `embedding`
field mixed modalities, "similarity" was standing in for usefulness, and there
was no held-out evaluation. The audit graded 75 claims by evidence strength
and deleted the ones that could not be supported. Everything above is what
replaced them.

---

## My contribution

Single author. Across both phases:

- **Nexus integration.** Browser OAuth lifecycle, deterministic session
  fingerprinting from document entities, transactional insert with an exact-undo
  receipt, tested against the official offline document validator.
- **Retrieval and ranking.** Versioned representation contract with model
  lineage, RRF fusion, six comparison methods, a capacity ladder with a hard
  parameter budget enforced by unit test.
- **Research design.** Preregistered protocol, label-compatible metrics
  enforced in code, per-item license manifest for the pretraining corpus, blind
  pairwise annotation flow, anonymized export.
- **The evidence audit.** Including deciding which of my own earlier claims to
  delete.
- **Full stack.** FastAPI backend, Next.js frontend, Cloud Run + Vercel deploy.

---

## License

Code and domain skills: [Apache 2.0](LICENSE).
The accompanying ISMIR 2026 Late-Breaking/Demo paper is licensed under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
