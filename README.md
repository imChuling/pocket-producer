# Pocket Producer

> An agentic creative memory system for music makers — capture fleeting ideas,
> reconnect them with past fragments, and move unfinished work forward.

**Submission**: Google Cloud Rapid Agent Hackathon 2026 · MongoDB Track

**Tagline**: *Your creative atlas, in your pocket.*

**Live Demo**: https://pocketproducer.vercel.app
**Demo Video**: https://youtu.be/yZbZ7jUQ_0A

---

## The Problem

Every songwriter has a graveyard of voice memos, lyric notes, and
half-finished demos scattered across their phone. It sounds like this:

| Problem | What creators say |
|---|---|
| **Fragmentation** | "60+ voice memos on my phone, can't remember what any of them are" |
| **Lost connections** | "I hummed something last month that had potential, but I can't find it" |
| **Hidden relationships** | "Turns out that lyric and that piano motif were the same song all along" |
| **Unfinished song paralysis** | "30 incomplete songs. No idea which one to work on next" |

Tools in this space either write the song for you (Suno, Udio) or help you
record even more audio you'll never find again (voice memos with tags).
Neither touches the real bottleneck:

> **The creative bottleneck isn't output — it's memory of what you've already created.**

## The Solution

Pocket Producer is a grounded creative memory agent:

1. **Capture** — record audio or type text; Gemini 3 Flash listens and tags
   it (emotion, theme, structure, style) within seconds
2. **Reconnect** — MongoDB Atlas Vector Search finds semantically similar past
   fragments; an ADK Memory Agent classifies relationships using domain skills
3. **Move forward** — a Producer Agent decides project grouping, computes a
   Rescue Score, and suggests one concrete next step you can do in 30 minutes

Pocket Producer doesn't write songs for you. It remembers what you've created
and connects what should belong together.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 16 PWA)                                      │
│  Deployed on Vercel                                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS + Firebase Auth Token
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI on Cloud Run)                                  │
│                                                                  │
│  ┌─── Fast Capture Path ────────────────────────────────────┐   │
│  │ Audio → GCS upload → librosa features + Gemini multimodal │   │
│  │ tagging (with music-tagging skill) → Voyage AI embedding  │   │
│  └───────────────────────────────────────────────────────────┘   │
│                       │                                          │
│                       ▼                                          │
│  ┌─── Agentic Memory Path (Google ADK) ─────────────────────┐   │
│  │ Producer Agent (root) → Memory Agent (AgentTool)          │   │
│  │                                                           │   │
│  │ Memory: vector search → relationship classification       │   │
│  │ Producer: project grouping → Rescue Score → next action   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                       │                                          │
│           MongoDB MCP Server (co-located)                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐    ┌─────────────────────┐
│ MongoDB Atlas    │    │ Google Cloud Storage │
│ (Vector Search)  │    │ (audio files)       │
│                  │    │                     │
│ Collections:     │    └─────────────────────┘
│ • fragments      │
│ • projects       │
│ • user_dna       │
│ • notifications  │
└──────────────────┘
```

The ingest flow keeps perception fast and lets memory work take its time:
Gemini multimodal tagging runs directly (a couple of seconds for text, ~15s
for audio), while the ADK agent pipeline does relationship discovery and
project decisions in the background.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical breakdown.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent Framework** | Google ADK (`google-adk` v1.25+) with 5 open-source domain skills |
| **LLM** | Gemini 3 Flash (`gemini-3-flash-preview`) for agent reasoning and audio tagging; Gemini 3.1 Flash-Lite for text tagging |
| **Database** | MongoDB Atlas with Vector Search (cosine, 1024-dim) |
| **MCP** | MongoDB MCP Server (HTTP transport, co-located in Cloud Run container) |
| **Embeddings** | Voyage AI (`voyage-3`, 1024-dim) — MongoDB-provided |
| **Audio Analysis** | librosa (BPM, key, mode, energy curve, brightness, onset density) |
| **Transcription** | Gemini 3 Flash multimodal — listens to audio directly, no separate STT step |
| **Auth** | Firebase Authentication |
| **Storage** | Google Cloud Storage (audio files) |
| **Backend** | FastAPI + uvicorn, deployed on Cloud Run |
| **Frontend** | Next.js 16, React 19, Tailwind CSS v4, Recharts, Motion, shadcn/ui |
| **Deployment** | Cloud Run (backend) + Vercel (frontend) |
| **License** | Apache 2.0 |

---

## Skills Layer

> If you only read one part of this repo, read the skills. Five of them,
> all open source, encoding actual music domain knowledge — and loaded via
> progressive disclosure so they don't blow up the context window.

Pocket Producer applies the
[ADK Skills system](https://google.github.io/adk-docs/skills/) to the music
creation domain. Skills separate **domain rules** from **agent logic**, making
both independently testable and reusable.

| Skill | Files | Lines | Purpose | Consumer |
|---|---|---|---|---|
| [`music-tagging`](backend/skills/music-tagging/) | 6 | ~2,350 | Emotion, theme, structure, and style taxonomy for fragment tagging | Gemini tagging pipeline |
| [`relationship-rules`](backend/skills/relationship-rules/) | 1 | ~800 | 4-class relationship classification with multi-signal fusion | Memory Agent |
| [`musical-knowledge`](backend/skills/musical-knowledge/) | 4 | ~1,640 | Key compatibility, tempo rules, genre conventions (35 styles) | Memory + Producer Agents |
| [`rescue-scoring`](backend/skills/rescue-scoring/) | 1 | ~650 | Rescue Score interpretation, explanation, and next-action generation | Producer Agent |
| [`refusal-rules`](backend/skills/refusal-rules/) | 1 | ~530 | When to refuse, request input, or escalate | All agents |

**~5,970 lines** of domain knowledge across 13 markdown files + 1 JSON asset,
all [Apache 2.0 licensed](LICENSE).

Skills load via **progressive disclosure** — only metadata (~100 tokens/skill)
at startup; full rules load on demand. See [SKILLS.md](SKILLS.md) for details.

---

## Agent Pipeline

Two real ADK agents run in the ingest pipeline:

**Producer Agent** (root, `gemini-3-flash-preview`) orchestrates:
- Calls the Memory Agent as an ADK `AgentTool` for relationship discovery —
  the analysis returns to Producer as a tool result, so control never leaves
  the root agent
- Executes project decisions (join / create / bridge)
- Computes Rescue Score and generates next actions
- Tools: `memory` (AgentTool), `create_project_from_fragments`, `attach_fragment_to_project`, `refresh_project_score`, `generate_project_title`, `generate_next_action`
- Skills: `rescue-scoring`, `musical-knowledge`, `refusal-rules`, `music-tagging`

**Memory Agent** (agent-as-a-tool, `gemini-3-flash-preview`) grounds decisions:
- Vector search via MongoDB Atlas (`$vectorSearch` aggregation)
- Relationship classification using domain skills
- Optional: MongoDB MCP read tools for demo visibility
- Tools: `get_fragment_context`, `vector_search_fragment_neighbors`, `get_project_context`
- Skills: `relationship-rules`, `musical-knowledge`, `refusal-rules`

**Catcher Agent** exists in the codebase but is bypassed in the live pipeline:
direct Gemini multimodal calls turned out 3x faster for tagging, so the agent
is kept for batch reprocessing and Agent Engine deployment instead.

---

## Data Safety

- Firebase Auth verifies every API request
- Every database read and write, in REST endpoints and agent tools alike, is
  scoped to the authenticated `user_id`
- Creator-provided text is sanitized and wrapped in `<creator_fragment>` tags to
  prevent prompt injection; regex patterns flag suspicious input
- Fragment deletion removes both the MongoDB document and the GCS audio object
- Audio is served through authenticated streaming endpoints, not public GCS URLs
- The agent's MongoDB MCP query tool is read-only, limited to a collection
  allowlist, and **user-scoped at the tool layer**: `user_id` is injected
  after the model-supplied filter, so neither the model nor prompt-injected
  fragment content can read another user's data

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB (local or Atlas)
- Google Cloud project with Gemini API access
- Voyage AI API key

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Copy and fill environment variables
cp .env.example .env

# Run tests
pytest tests/test_rescue_score.py

# Start the server
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

### Docker (full stack)

```bash
docker compose up
```

This starts MongoDB, MongoDB MCP Server, and the backend. The frontend runs
separately via `pnpm dev` or Vercel.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ingest` | Upload audio or text fragment |
| `GET` | `/api/fragments` | List user's fragments |
| `GET` | `/api/fragments/:id` | Get single fragment |
| `GET` | `/api/fragments/:id/audio` | Stream audio (with Range support) |
| `POST` | `/api/fragments/:id/edit-text` | Edit text with AI re-analysis |
| `POST` | `/api/fragments/:id/tags` | Update tags manually |
| `POST` | `/api/fragments/:id/title` | Update fragment title |
| `POST` | `/api/fragments/:id/reanalyze` | Re-run Gemini pipeline on one fragment |
| `POST` | `/api/fragments/:id/delete` | Delete fragment + GCS audio |
| `POST` | `/api/fragments/:id/group-with-agent` | Run agent pipeline on one fragment (debug) |
| `GET` | `/api/projects` | List projects (sorted by Rescue Score) |
| `GET` | `/api/projects/:id` | Get project with fragments |
| `GET` | `/api/dna` | Creative DNA insights |
| `GET` | `/api/notifications` | Resurrect notifications |
| `POST` | `/api/notifications/:id/read` | Mark notification read |
| `POST` | `/api/notifications/read-all` | Mark all notifications read |
| `POST` | `/api/reprocess-projects` | Re-run agent pipeline on existing fragments |
| `POST` | `/api/reanalyze-all` | Re-run full Gemini pipeline on all fragments |
| `POST` | `/api/reset-projects` | Delete all projects (re-grouping) |
| `POST` | `/api/fix-stuck` | Fix fragments stuck in processing |
| `GET` | `/api/agent-memory/status` | Agent pipeline status |
| `POST` | `/api/jobs/dna` | Trigger DNA insights job |
| `POST` | `/api/jobs/resurrect` | Trigger resurrect notifier job |

---

## Verifying the Agent Pipeline

### Required tech, invoked at runtime

All three hackathon-required technologies are imported and called on every
fragment ingest — not just named in this README:

| Requirement | Where it runs | Code |
|---|---|---|
| **Gemini 3** | `gemini-3-flash-preview` powers the Producer + Memory Agents and audio tagging; `gemini-3.1-flash-lite` tags text — all via Vertex AI (`genai.Client(vertexai=True)`, global endpoint) | [`api/pipeline.py`](backend/api/pipeline.py), [`agents/producer.py`](backend/agents/producer.py), [`agents/memory.py`](backend/agents/memory.py) |
| **Google Cloud Agent Builder (ADK)** | `google.adk` `LlmAgent` + `Runner` + `AgentTool` execute the Producer → Memory pipeline on every ingest; skills load via ADK `SkillToolset` | [`agents/_runner.py`](backend/agents/_runner.py), [`agents/producer.py`](backend/agents/producer.py) |
| **MongoDB MCP Server** | Runs inside the Cloud Run container (`start.sh`); every vector search is an `aggregate` call through the MCP protocol, and the Memory Agent's `mongo_mcp_find` tool routes project lookups through it | [`backend/start.sh`](backend/start.sh), [`agents/memory.py`](backend/agents/memory.py) |

No competing AI or cloud services: embeddings are Voyage AI
(MongoDB-provided, per MongoDB track rules), auth is Firebase, and all agent
infrastructure runs on Google Cloud (Cloud Run, Vertex AI, Cloud Storage,
Cloud Scheduler).

### How it triggers

Every fragment with an embedding triggers the agent pipeline automatically
(`process_fragment_background` → `memory_and_project` →
`group_fragment_with_agents`).

To observe it directly:

```bash
# With docker compose running:
docker compose logs -f backend | grep -E "Agent tool call|Producer pipeline|via MCP"
```

### Observed in production (June 2026)

Real log excerpts from the deployed Cloud Run service — every claim below is
reproducible by uploading a fragment:

**MongoDB MCP vector search** (Memory Agent routing `$vectorSearch` through
the MongoDB MCP Server):

```
INFO:agents.memory:Memory Agent: MCP enabled, project lookups will use mongo_mcp_find (user-scoped)
INFO:agents.memory:Vector search via MCP: 5 neighbors for 6a2a0767... (threshold=0.55)
```

**Full agentic decision** (Producer calls Memory as an AgentTool, then
executes project tools and returns structured JSON):

```
Agent tool call: agent=producer tool=memory
Agent tool call: agent=producer tool=generate_project_title
Agent tool call: agent=producer tool=create_project_from_fragments
Agent tool call: agent=producer tool=generate_next_action
Agent tool call: agent=producer tool=refresh_project_score
Producer pipeline completed: events=11 result={'decision': 'new_project',
  'reasoning': 'Both fragments share strong thematic alignment through rain
  imagery and matching slow, minor-key musical profiles.',
  'narrative': "I was listening to your new line, 'the rain is me,' and it
  immediately called back to that minor-key piano motif you recorded. Both
  carry such a heavy, beautiful sense of acceptance. I've grouped them
  together as 'The Rain Is Me' because they feel like they're breathing the
  same air.", ...}
```

**Refusal rules firing on real input** — a tester uploaded a cover of a
well-known song, and the `refusal-rules` skill declined to group it:

```
Producer pipeline completed: result={'decision': 'no_group',
  'reasoning': 'Refused to classify: The input fragment contains copyrighted
  lyrics from a known song ("Stairway to Heaven").', ...}
```

The skill layer is not prompt decoration — it changes agent behavior in
production.

In the UI, grouped fragments display the agent's `connection_reason`,
`connection_types`, and a first-person `agent_narrative` — the multi-step
reasoning made visible, not just tags.

---

## License

[Apache 2.0](LICENSE) — including all 5 domain skills.
