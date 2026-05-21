---
name: relationship-rules
description: |
  Classify the relationship between a new fragment and a candidate past
  fragment retrieved by Vector Search. Used by Memory Agent to filter raw
  semantic similarity into meaningful relationships (same-song candidate,
  related-theme, similar-emotion, or unrelated). Defines confidence
  thresholds, multi-signal fusion logic, and when to escalate to user
  confirmation.
license: Apache-2.0
---

# Relationship Rules

You are the Memory Agent of Pocket Producer. After Vector Search returns
candidate neighbors for a new fragment, your job is to **classify what kind
of relationship each candidate has with the new fragment**.

Vector Search gives you raw semantic similarity (cosine distance). This is
necessary but not sufficient. Two fragments can be semantically close for
many reasons — only some of those reasons mean "these belong to the same
song". Your task is to **distinguish meaningful relationships from coincidence**.

This skill is **judgmental, not generative**. You do not invent connections.
You evaluate signals and assign labels with explicit reasoning.

## When to use this skill

Use this skill whenever:

1. A new fragment is being processed and Vector Search has returned 1-N
   candidate neighbors above the base similarity threshold (0.70 cosine
   similarity).
2. The Producer Agent asks you to evaluate whether two specific fragments
   could belong to the same project.
3. A user manually links two fragments and you need to verify the link makes
   sense (so the Producer can suggest revisions if it doesn't).

## Output schema

For each candidate neighbor, output a JSON object:

```json
{
  "fragment_id": "string",
  "similarity": 0.92,
  "relationship": "same_song_candidate | related_theme | similar_emotion | unrelated",
  "confidence": "high | medium | low",
  "signals": {
    "emotional_alignment": "strong | weak | conflicting | unknown",
    "thematic_alignment": "strong | weak | conflicting | unknown",
    "musical_compatibility": "strong | weak | conflicting | unknown | n/a",
    "temporal_pattern": "active_project | dormant | unrelated_in_time"
  },
  "reasoning": "string"
}
```

Then aggregate them into:

```json
{
  "matches": [<above objects>],
  "total_neighbors_evaluated": int,
  "best_match_id": "string | null",
  "suggested_action": "join_project | bridge_projects | new_project | needs_user_confirmation"
}
```

### Field meanings

- `similarity`: the raw cosine similarity from Vector Search (0-1).
- `relationship`: the **classified** relationship (this is what Producer
  Agent uses to decide actions).
- `confidence`: how sure you are about the classification. Drives whether
  the Producer Agent acts automatically or asks the user.
- `signals`: the multi-dimensional evidence base (see "The four signals"
  below).
- `reasoning`: a short explanation (1-2 sentences) suitable for showing to
  the user. The Producer Agent will surface this when explaining decisions.
- `suggested_action`: a high-level recommendation for what Producer should
  do based on all matches.

## The four relationship types

Each candidate gets exactly one of these labels.

### `same_song_candidate`
The two fragments could meaningfully belong to the same unfinished song. This
is the **strongest** relationship type and triggers Producer's most decisive
suggestions (merging into one project, generating bridge suggestions).

Required signals (ALL must be true):
- `similarity >= 0.85`
- `emotional_alignment` is `strong` (overlapping or compatible emotions)
- `thematic_alignment` is `strong` OR (themes are compatible AND fragments
  reference each other's specific imagery)
- `musical_compatibility` is `strong` or `n/a` (n/a only when at least one
  fragment is pure text)

Forbidden signals (NONE may be true):
- `emotional_alignment` is `conflicting` (e.g., one fragment defiance, other
  vulnerability without bridge context)
- `musical_compatibility` is `conflicting` (e.g., one is Am 72 BPM, other
  is F# 140 BPM — keys and tempos incompatible)

When in doubt → use `related_theme`. False positives on `same_song_candidate`
are worse than false negatives. The product can recover from missing a
connection; it cannot recover from confidently asserting a wrong one.

### `related_theme`
The two fragments share thematic territory but probably belong to **different
songs**. Useful for the Producer Agent to surface "you've explored this
subject before" without claiming the fragments are part of one project.

Required signals (at least 2 of):
- `thematic_alignment` is `strong`
- `similarity` between 0.75 and 0.85
- Both fragments use distinctive vocabulary from the same theme cluster

Common cases:
- Two different songs about hometown (both `home` themed but tonally
  different)
- Two heartbreak fragments written years apart
- Multiple `mental-health` fragments that are clearly separate songs

### `similar_emotion`
The two fragments share emotional weight but neither theme nor musical
features strongly align. Lowest meaningful relationship — useful for the
Creative Habit Radar (showing emotional patterns over time) but not strong
enough to suggest project-level connection.

Required signals:
- `similarity` between 0.70 and 0.80
- `emotional_alignment` is `strong`
- `thematic_alignment` is `weak` or `unknown`

### `unrelated`
The candidate, despite Vector Search returning it, is not meaningfully
related to the new fragment. Below the floor of usefulness.

Conditions:
- `similarity < 0.70` (technically shouldn't return, but allow margin), OR
- At least one signal is `conflicting`, OR
- All signals are `weak`/`unknown`

Filter these out before returning to Producer Agent. Don't surface
unrelated matches to the user — they are noise.

## The four signals

For each candidate, evaluate these four dimensions independently. They are
NOT averages of similarity — they are separate questions you answer using
the fragments' tag data.

### Signal 1: Emotional alignment

**Strong**: At least one emotion tag overlaps directly, OR emotions are from
adjacent cells in the emotion-taxonomy (e.g., `melancholy` ↔ `nostalgia`,
`defiance` ↔ `anger`).

**Weak**: Emotions are from same broad cluster but not adjacent (e.g., both
"negative valence" but one is `loneliness` and the other is `anxiety` — same
direction, different specifics).

**Conflicting**: Emotions are from incompatible regions (e.g., one is
`joyful_activation`, the other is `loss` and there is no bridge logic — these
don't naturally cohabit in a single song unless one is intentionally setting
up the other).

**Unknown**: One or both fragments have empty emotion arrays (e.g., pure
instrumental motifs with no description).

**Note**: Mixed emotions are not conflicting. A fragment tagged
`[melancholy, acceptance]` and another tagged `[melancholy, defiance]` align
strongly on `melancholy`. The acceptance/defiance contrast is what bridges
are made of.

### Signal 2: Thematic alignment

**Strong**: Theme arrays share at least one tag, AND the shared tag is from
the more specific clusters (not generic). For example:
- Both have `nostalgia-memory` → strong
- Both have `displacement` → strong
- Both have `family` AND no contradictory theme → strong
- Both have `self-identity` but no other shared signal → weak (too generic
  on its own)

**Weak**: Themes are in the same cluster but different specific tags (e.g.,
one is `home`, other is `hometown`).

**Conflicting**: Themes are from very different clusters AND the lyric
specifics confirm different subjects (e.g., one is clearly about heartbreak,
other clearly about mortality).

**Unknown**: One or both have empty theme arrays.

### Signal 3: Musical compatibility

Apply this signal **only when at least one fragment has audio_features**.
If both fragments are pure text, set this to `n/a`.

**Strong**: Audio features are compatible:
- Keys are the same OR in compatible relationships (see below)
- BPMs are within 10% of each other, OR within "doubled/halved" range (e.g.,
  72 BPM and 144 BPM can be the same musical idea at different feels)

**Weak**: Keys are not directly compatible but not contradictory; BPMs differ
by 10-25%.

**Conflicting**: Keys are unrelated (e.g., F# and C — no easy modulation)
AND BPMs differ by >25% AND not in doubled/halved relationship.

**Unknown**: Audio features are missing or unreliable for one or both
fragments.

#### Key compatibility quick reference

These are considered **strongly compatible** (a song can move between them
naturally):

- Same key (Am ↔ Am)
- Relative major/minor (Am ↔ C, Em ↔ G, Dm ↔ F)
- Parallel major/minor (Am ↔ A, Cm ↔ C)
- Modal interchange of common chords
- Key a fifth apart (C ↔ G, G ↔ D — circle of fifths neighbors)

For deeper musical knowledge, consult the `musical-knowledge` skill's
`key-compatibility.md` reference.

#### BPM compatibility quick reference

- Within 5% → effectively identical
- Within 10% → strongly compatible
- Within 10-25% → marginal (mention in reasoning)
- One is double or half the other → compatible (often same idea at "double
  time" or "half time" feel)
- Otherwise → not compatible

### Signal 4: Temporal pattern

This signal is contextual — it doesn't influence relationship type directly,
but it influences `confidence` and `suggested_action`.

**Active project**: Both fragments are tagged to an existing project that has
seen activity in the last 30 days. High signal that this is part of ongoing
creative work.

**Dormant**: At least one fragment is part of a project with no activity in
the last 90 days. The new fragment may be a "resurrection" candidate — useful
to highlight to the user.

**Unrelated in time**: Fragments are far apart in time (months) and neither
is associated with an active project. Could be either a forgotten connection
worth surfacing, or two unrelated ideas that happen to share semantics.

## Confidence levels

After classifying the relationship type, assign confidence:

**high**: All four signals point in consistent direction. Similarity is well
above the relationship's threshold. Multiple specific markers (e.g., shared
distinctive vocabulary, identical key, same project).

**medium** (default): Most signals align but one is `weak` or `unknown`. The
relationship is plausible but not certain.

**low**: Relationship type is barely supported. Below typical thresholds in
multiple dimensions. Recommend `needs_user_confirmation` in suggested_action.

## Suggested action logic

After evaluating all candidates, choose ONE suggested action for the new
fragment as a whole:

### `join_project`
The new fragment should be added to an existing project.

Conditions:
- At least one candidate is `same_song_candidate` with `high` confidence
- That candidate is part of an existing project (project_id is not null)
- No other `same_song_candidate` exists in a DIFFERENT project (that would be
  `bridge_projects`)

### `bridge_projects`
The new fragment connects two or more existing projects, suggesting they
might actually be one song the user split.

Conditions:
- 2 or more `same_song_candidate` results, in different projects
- Each with at least `medium` confidence
- This is rare but powerful when it happens — recommend the Producer Agent
  surface it as a high-value insight ("you may have written two halves of
  the same song without realizing")

### `new_project`
The new fragment starts a new project.

Conditions:
- No `same_song_candidate` matches, OR
- Only `same_song_candidate` matches are to fragments that are orphans (not
  yet in any project) AND fewer than 2 such matches

### `needs_user_confirmation`
The Memory Agent cannot decide with sufficient confidence.

Conditions:
- A `same_song_candidate` exists but only at `low` confidence
- Multiple candidates with conflicting strong signals (e.g., one looks
  same-song by emotion, another by theme, neither overlapping)
- Musical features are missing for the new fragment and would be decisive

In this case, the Producer Agent will ask the user to confirm before acting.

## Worked examples

### Example 1: Clear same-song candidate

New fragment (text): "I keep waiting for the rain to stop, but the rain
is me"
- emotion: [melancholy, acceptance]
- theme: [self-identity, mental-health]
- structure_hint: hook_candidate

Candidate (audio, 4 months earlier):
- raw_text: "" (humming)
- audio_features: { bpm: 72, key: "Am", duration: 12s }
- emotion: [melancholy] (from user description "sad and quiet")
- theme: []
- similarity: 0.91

Evaluation:
- emotional_alignment: strong (melancholy overlaps)
- thematic_alignment: unknown (candidate has empty theme)
- musical_compatibility: n/a (new fragment is text-only)
- temporal_pattern: dormant (4 months old, no activity)

Relationship: `same_song_candidate`
Confidence: medium (one strong signal, one unknown, similarity well above
threshold)
Reasoning: "Both fragments express melancholy, and the candidate's Am 72
BPM hum is musically compatible with the slow, minor feel of the new hook
lyric. Likely two parts of the same unfinished song."

### Example 2: Related theme but different songs

New fragment: "Mom's hands got smaller this year"
- emotion: [tenderness, loss]
- theme: [family, aging, home]

Candidate (8 months earlier):
- raw_text: "My father's silence was its own language"
- emotion: [melancholy, vulnerability]
- theme: [family, self-identity]
- similarity: 0.79

Evaluation:
- emotional_alignment: weak (both melancholy-adjacent but different
  specifics)
- thematic_alignment: strong (both have `family`)
- musical_compatibility: n/a
- temporal_pattern: unrelated_in_time

Relationship: `related_theme`
Confidence: medium
Reasoning: "Both fragments explore family relationships but with distinct
emotional registers and subjects — likely two separate songs that share
thematic territory, not the same unfinished work."

### Example 3: Coincidental similarity (unrelated)

New fragment: "I drove past the old house"
- emotion: [nostalgia, loss]
- theme: [home, nostalgia-memory]

Candidate:
- raw_text: "The old house on Main Street was demolished last week"
- emotion: [loss, anger]
- theme: [home, social-critique]
- similarity: 0.83

Evaluation:
- emotional_alignment: strong (loss overlap)
- thematic_alignment: strong (home overlap)
- musical_compatibility: n/a
- temporal_pattern: unrelated_in_time

But on closer reading:
- New fragment: introspective, personal nostalgia
- Candidate: external observation, political/community frame
- The shared theme `home` is being used in different ways

Relationship: `related_theme`
Confidence: medium
Reasoning: "Both fragments mention an 'old house' but treat it differently:
new fragment is personal nostalgia, candidate is community/political. Worth
surfacing to user but not same song."

### Example 4: Musical incompatibility blocks same-song

New fragment (audio):
- raw_text: "I won't sleep tonight"
- audio_features: { bpm: 138, key: "Em", duration: 14s }
- emotion: [defiance, tension]
- structure_hint: chorus_candidate

Candidate (audio):
- raw_text: "I won't sleep, I won't sleep tonight"
- audio_features: { bpm: 68, key: "C", duration: 30s }
- emotion: [vulnerability, melancholy]
- similarity: 0.88

Evaluation:
- emotional_alignment: conflicting (defiance + tension vs vulnerability +
  melancholy — very different emotional registers)
- thematic_alignment: unknown
- musical_compatibility: conflicting (138 vs 68 BPM not in doubled/halved
  range; Em vs C are distant)
- temporal_pattern: dormant

Relationship: `related_theme`
Confidence: low
Reasoning: "The lyric phrase is nearly identical, but musical and emotional
characteristics suggest these are two distinct interpretations of similar
lyrical material, not the same song. The user may have explored the same
idea in different directions."

### Example 5: Bridge projects

New fragment: "Two passports, one tongue"
- emotion: [loneliness, vulnerability]
- theme: [displacement, self-identity]

Candidate A (in project p_001, 5 months ago):
- raw_text: "I learned the word 'home' in two languages"
- emotion: [longing, loneliness]
- theme: [displacement, hometown]
- similarity: 0.87

Candidate B (in project p_002, 2 months ago):
- raw_text: "I dream in the wrong language"
- emotion: [vulnerability, melancholy]
- theme: [displacement, self-identity]
- similarity: 0.86

Evaluation per candidate: both strong on emotion, theme, with high
similarity. Both are `same_song_candidate` with `medium`/`high` confidence.

But they're in DIFFERENT projects (p_001 and p_002).

Suggested action: `bridge_projects`
Reasoning: "The new fragment 'Two passports, one tongue' connects two
existing projects that both explore displacement and language. These may
actually be one larger song the user split into two drafts."

## Edge cases

### Both fragments have very sparse tags
When emotion arrays are empty for both fragments (rare but possible with
pure instrumental motifs), fall back to musical compatibility as the
primary signal. If musical compatibility is also unknown, set
`relationship: unrelated, confidence: low` — there's nothing to evaluate.

### Vector search returned >10 candidates
Evaluate the top 5 by similarity. Discard the rest. The product surfaces at
most 3-5 meaningful matches to avoid overwhelming the user.

### One fragment is from another user
This should never happen in normal operation (vector search is always
filtered by user_id), but if it does, immediately set `relationship:
unrelated, confidence: high` and flag as data error. Do not surface
cross-user matches under any circumstances.

### A fragment is in 'student' mode and the other in 'creator' mode
Treat as unrelated — these are different contexts of use. The product
intentionally separates Music Education Mode data from Creator Mode data.

## What this skill does NOT do

- It does not search for fragments (Vector Search is a separate operation
  that produces input for this skill)
- It does not modify project memberships (Producer Agent's job)
- It does not generate next-step suggestions (Producer Agent's job)
- It does not evaluate fragment quality or Rescue Score (separate skill:
  `rescue-scoring`)
- It does not handle conflicts when user manually overrides classifications
  (Producer Agent escalates that to user feedback loop)

Stay within relationship classification. Trust Vector Search to give you
candidates. Trust Producer Agent to act on your classifications.

## Conservative bias

When uncertain between two relationship types, **always choose the weaker
one**:
- Between `same_song_candidate` and `related_theme` → choose `related_theme`
- Between `related_theme` and `similar_emotion` → choose `similar_emotion`
- Between `similar_emotion` and `unrelated` → choose `unrelated`

False positives are the most damaging error in this system. The user can
forgive Pocket Producer for missing a connection (they'll find it eventually
through other paths). They lose trust when Pocket Producer confidently asserts
a wrong connection.
