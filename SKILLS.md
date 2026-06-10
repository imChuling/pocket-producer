# Skills

Pocket Producer ships 5 open-source ADK skills — domain knowledge encoded as
structured markdown, loaded by [Google ADK](https://github.com/google/adk-python)
via progressive disclosure. All skills are licensed under
[Apache 2.0](LICENSE).

These skills represent the **semantic layer** of the product: they define how
fragments are tagged, how relationships are classified, how scores are
interpreted, and when agents should refuse to act. Changing a skill changes
agent behavior across the entire system — no prompt rewrites needed.

---

## Index

| Skill | Files | Lines | Location |
|---|---|---|---|
| [music-tagging](#music-tagging) | 6 | ~2,350 | [`backend/skills/music-tagging/`](backend/skills/music-tagging/) |
| [relationship-rules](#relationship-rules) | 1 | ~800 | [`backend/skills/relationship-rules/`](backend/skills/relationship-rules/) |
| [musical-knowledge](#musical-knowledge) | 4 | ~1,640 | [`backend/skills/musical-knowledge/`](backend/skills/musical-knowledge/) |
| [rescue-scoring](#rescue-scoring) | 1 | ~650 | [`backend/skills/rescue-scoring/`](backend/skills/rescue-scoring/) |
| [refusal-rules](#refusal-rules) | 1 | ~530 | [`backend/skills/refusal-rules/`](backend/skills/refusal-rules/) |
| **Total** | **13** | **~5,970** | |

All 5 skills follow a unified template: Purpose, When NOT to use, Input
schema, Output schema, Procedure, Worked examples, Common mistakes, and
Edge cases (where applicable).

---

## music-tagging

**Purpose**: Convert raw fragment input (audio transcript, text, emoji) into
structured metadata that downstream agents use for search and relationship
discovery.

**Consumer**: Gemini multimodal tagging pipeline (loaded as system context)
and Catcher Agent (loaded via ADK SkillToolset).

**Structure**:

```
music-tagging/
├── SKILL.md                    # Core rules, tagging procedure, output schema
├── references/
│   ├── emotion-taxonomy.md     # 20 GEMS-based emotion tags with definitions
│   ├── theme-taxonomy.md       # 24 theme categories with decision tree
│   ├── structure-hints.md      # 7 structure types (verse, chorus, hook, bridge, etc.)
│   └── style-vocabulary.md     # 35 style tags across 9 clusters with audio markers
└── assets/
    └── tagging-examples.json   # 30 worked examples for calibration
```

**Key design decisions**:
- Emotion taxonomy is based on GEMS (Geneva Emotional Music Scales), adapted
  for fragment-level tagging rather than full-song annotation
- Tags are **descriptive, not generative** — the skill describes what is present,
  never invents features without evidence
- `needs_user_input` flag triggers when input is too sparse for confident tagging
- Worked examples provide calibration for ambiguous cases (mixed emotions,
  non-English input, pure instrumental)

**Style taxonomy** (35 tags, 9 clusters):
- Singer-songwriter: `indie-folk`, `singer-songwriter`, `acoustic-ballad`
- Pop: `pop`, `alt-pop`, `bedroom-pop`, `synth-pop`, `art-pop`, `dream-pop`
- Hip-hop / R&B / Soul: `hip-hop`, `trap`, `r&b`, `soul`, `neo-soul`
- Jazz & Blues: `jazz`, `blues`, `fusion`
- Electronic: `electronic`, `ambient`, `lo-fi`
- Rock: `rock`, `indie-rock`, `soft-rock`, `post-rock`, `math-rock`,
  `shoegaze`, `psychedelic-rock`, `progressive-rock`
- Punk: `punk`, `post-punk`
- Heavy: `metal`, `metalcore`
- Other: `experimental`, `world-fusion`

Each tag includes description, audio markers, reference artists, Spotify genre
mapping, and distinction notes from similar tags.

---

## relationship-rules

**Purpose**: Classify the relationship between a new fragment and each candidate
neighbor returned by vector search. Converts raw cosine similarity into
meaningful relationship types.

**Consumer**: Memory Agent (loaded via ADK SkillToolset).

**Structure**:

```
relationship-rules/
└── SKILL.md    # Classification rules, signal fusion, confidence thresholds
```

**4-class taxonomy**:

| Class | Meaning | Required evidence |
|---|---|---|
| `same_song_candidate` | Likely part of the same song | ≥2 strong signals (lyrical continuity, structural complement, shared imagery + compatible key/tempo) |
| `related_theme` | Shared thematic content | Overlapping theme tags or imagery, but insufficient evidence for same-song |
| `similar_emotion` | Shared emotional quality | Overlapping emotion tags without thematic or musical connection |
| `unrelated` | Semantically close but coincidental | Default when signals are weak or conflicting |

**Multi-signal fusion**: the skill evaluates four signal channels —
emotion overlap, thematic continuity, musical compatibility, and temporal
context — and requires convergence before asserting strong relationships.

**Conservative bias**: when uncertain, the skill instructs agents to choose the
weaker relationship type. A wrong connection damages trust more than a missed
one.

**Bridge detection**: when a new fragment is related to fragments from two
different projects, the skill outputs `bridge_projects` as a suggested action.

**10 worked examples** covering: high-confidence same-song, related theme,
similar emotion, true unrelated, full-convergence active project, ambiguous
needs-user-confirmation, non-English fragment (Chinese), and edge cases.

---

## musical-knowledge

**Purpose**: Objective music theory rules for evaluating compatibility between
fragments. Purely referential — answers questions, doesn't act on fragments.

**Consumer**: Memory Agent and Producer Agent (loaded via ADK SkillToolset).

**Structure**:

```
musical-knowledge/
├── SKILL.md                    # Key/tempo/style compatibility algorithms, worked examples
└── references/
    ├── key-compatibility.md    # Complete key reference tables, circle of fifths
    ├── tempo-rules.md          # BPM zones, half/double-time, normalization
    └── genre-conventions.md    # Conventions for all 35 style tags
```

**L2 content** (SKILL.md, promoted from references for agent accessibility):
- Complete major/minor key reference tables (24 keys)
- `key_compatible()` and `tempo_compatible()` pseudocode algorithms
- BPM strong-range table by common BPMs
- Style compatibility tables: 30 compatible pairs, 17 possible pairs, 14 unlikely pairs
- Genre conventions quick reference for all 35 style tags (BPM, keys, structure)
- Modal scale mapping (Dorian, Phrygian, etc. → parent key)
- Common songwriter tempo categories (7 categories)

**Key edge cases handled**:
- librosa relative-key confusion (most common detection error)
- Very short fragments (< 5 seconds) → tempo unreliable
- Extreme BPM normalization (> 200 → halve, < 40 → double)
- Enharmonic equivalents (Db = C#, Gb = F#, Ab = G#)
- Trap half-time detection (70-90 BPM detected, 140-180 felt)
- Math-rock meter changes → tempo compatibility set to `unknown`
- Percussive audio → key unknown, evaluate tempo only

**10 worked examples**, **8 common mistakes**, **7 edge cases**.

---

## rescue-scoring

**Purpose**: Define how the Producer Agent interprets, explains, and presents
the Rescue Score to users. The actual score computation is pure Python
(`backend/tools/rescue_score.py`) — the skill focuses on what the numbers
**mean** and what to **do** about them.

**Consumer**: Producer Agent (loaded via ADK SkillToolset).

**Structure**:

```
rescue-scoring/
└── SKILL.md    # Formula reference, interpretation, next-action generation, presentation
```

**Formula** (reference — computed by Python, not the agent):
`score = richness + structure_completeness + emotional_coherence + freshness`

| Component | Max | What it measures |
|---|---|---|
| Richness | 30 | Number of fragments + text volume |
| Structure | 30 | Presence of verse, chorus, hook, bridge, or near-complete demo |
| Coherence | 20 | How consistently fragments share a dominant emotion |
| Freshness | 20 | Days since most recent fragment activity |

**Agent's responsibilities** (what the skill teaches):
- **Next-action generation**: tables of specific actions by weakest component,
  with estimated times and musical-specificity rules (mention key, tempo,
  structural role when known)
- **Explanation generation**: templates by tier (high/medium/low/new), DO/DON'T
  language rules, score change narratives (up/down/unchanged)
- **Presentation context**: different emphasis for project list view, single
  project view, notification context (Resurrect), and conversation context

**Not a quality judgment**: a low score means the project lacks material,
structure, coherence, or recency — not that the song is bad.

**6 worked examples** focused on interpretation: high-tier next action,
structure gap, dormant project, new project, score increase, coherence drop.

---

## refusal-rules

**Purpose**: Define when and how agents should stop, refuse, request user input,
or escalate. Shared across all agents to ensure consistent boundary behavior.

**Consumer**: All agents — Catcher, Memory, Producer (loaded via ADK SkillToolset).

**Structure**:

```
refusal-rules/
└── SKILL.md    # 6 refusal categories, protocols, escalation paths, worked examples
```

**Core principle**: a polite refusal is always better than a confident mistake.

**Refusal categories**:
1. **Data sparsity** — input too short or ambiguous for confident tagging
2. **Uncertainty** — conflicting signals in relationship classification
3. **Copyright concern** — input appears to be someone else's published work
4. **Scope mismatch** — request falls outside Pocket Producer's domain
5. **Emotional safety** — content suggesting crisis or distress
6. **Technical limitation** — unsupported format or exceeds processing limits

**10 worked examples** covering: sparse lyric, conflicting signals, near-
copyright, out-of-scope request, emotional crisis, system uncertainty (mixed
ideas in upload), dark lyrics NOT triggering safety, "just do it" override,
audio quality issues, and copyright grey area (humming familiar melody).

---

## How Skills Are Loaded

### ADK Path (Agent Pipeline)

```python
# backend/agents/_skills_loader.py
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset

SKILLS_DIR = pathlib.Path(__file__).parent.parent / "skills"

def get_skill_toolset(skill_names: list[str]):
    skills = [load_skill_from_dir(SKILLS_DIR / name) for name in skill_names]
    return skill_toolset.SkillToolset(skills=skills)
```

Each agent declares which skills it needs:

```python
# Memory Agent
tools=[get_skill_toolset(["relationship-rules", "musical-knowledge", "refusal-rules"]), ...]

# Producer Agent
tools=[get_skill_toolset(["rescue-scoring", "musical-knowledge", "refusal-rules", "music-tagging"]), ...]

# Catcher Agent
tools=[get_skill_toolset(["music-tagging", "refusal-rules"]), ...]
```

### Direct Path (Tagging Pipeline)

For the fast capture path, `music-tagging` skill files are read directly and
injected as Gemini system context (`_load_tagging_skill_context` in
`api/pipeline.py`). This includes SKILL.md, all reference documents, and a
selection of 3 worked examples from `tagging-examples.json`.

The result is cached after first load, so subsequent tagging calls pay no
file I/O cost.

---

## Contributing

Skills are designed to be independently useful. If you're building music-related
agents, you can use these skills in your own ADK project:

```bash
cp -r backend/skills/music-tagging your-project/skills/
```

Each skill is self-contained — the SKILL.md frontmatter includes name,
description, and license. Reference files provide the detailed taxonomies
and rules.

**Style taxonomy coverage**: the 35-tag style vocabulary covers mainstream and
niche genres including math-rock, shoegaze, post-punk, progressive-rock,
neo-soul, fusion, metalcore, and others. Each tag includes Spotify genre
mapping for cross-referencing. See
[`style-vocabulary.md`](backend/skills/music-tagging/references/style-vocabulary.md)
for the full taxonomy.
