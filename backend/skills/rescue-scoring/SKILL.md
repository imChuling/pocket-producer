---
name: rescue-scoring
description: |
  Compute the Rescue Score for a project — a 0-100 indicator of how likely
  the project is to be successfully completed if the user invests more time
  in it. Used by Producer Agent to prioritize which unfinished projects to
  surface and act on. Defines four weighted components, edge cases, and
  guidance for how to present scores to users.
license: Apache-2.0
---

# Rescue Scoring

You are computing the **Rescue Score** for a project. The Rescue Score is a
0-100 number that estimates how likely a project is to be "rescued" — that
is, completed into a finished song — if the user invests another 30-60
minutes on it.

This is **not a quality judgment**. A low score does not mean the song is
bad. It means the project has less material, less structural completeness,
less coherence, or less recent activity — making it harder to finish from
its current state.

The Rescue Score is the product's most visible numerical output. Users will
glance at it to decide where to spend their limited creative time.
Therefore: it must be **honest, stable, and explainable**.

## When to use this skill

Use this skill whenever:

1. A new fragment is added to a project — recompute the project's score.
2. A project hasn't been recomputed in 7+ days but is queried — recompute.
3. The user manually requests a score recomputation.
4. Producer Agent needs to rank projects for surfacing to the user.

Do NOT use this skill:
- For individual fragments (fragments don't have Rescue Scores; only
  projects do).
- For new projects with 1 fragment (insufficient data — return null score
  or display "single-fragment project, needs more material").

## Output schema

```json
{
  "project_id": "string",
  "rescue_score": 78,
  "components": {
    "richness": 28,
    "structure_completeness": 24,
    "emotional_coherence": 18,
    "freshness": 8
  },
  "tier": "high | medium | low | new",
  "explanation": "string"
}
```

### Field meanings

- `rescue_score`: integer 0-100. The four components sum to this.
- `components`: each component's contribution (see "The four components"
  below).
- `tier`:
  - `high` if score >= 70
  - `medium` if 40 <= score < 70
  - `low` if score < 40
  - `new` if the project has < 2 fragments (score not computed)
- `explanation`: a 1-2 sentence human-readable summary suitable for
  showing to the user.

## The four components

Each component is bounded. Sum = total score.

### Component 1: Richness (0-30 points)

Measures **how much raw material** the project contains.

```
richness = min(30, fragment_count * 4 + total_text_length / 100)
```

Where:
- `fragment_count` = number of fragments associated with the project
- `total_text_length` = sum of `raw_text` character counts across all
  fragments

Examples:
- 1 fragment with 20 chars → 4 + 0 = 4 points
- 3 fragments with 200 chars total → 12 + 2 = 14 points
- 6 fragments with 500 chars total → 24 + 5 = 29 → capped to 29
- 10 fragments with 1500 chars total → 40 + 15 = capped to 30

**Why this metric**: A song with 5 distinct fragments has more material to
work with than one with 1 fragment. Length matters too (a fragment with
"feeling sad today" contributes less than one with a verse).

### Component 2: Structure completeness (0-30 points)

Measures **how many distinct structural sections** the project has.

```
section_types = set of structure_hint values across project's fragments
structure_completeness = (
    + 10 if "verse_candidate" in section_types
    + 10 if "chorus_candidate" in section_types
    +  5 if "hook_candidate" in section_types
    +  5 if "bridge_candidate" in section_types
)
```

Capped at 30. Other structure_hints (`melodic_motif`, `lyric_fragment`)
don't contribute — they're undifferentiated material.

Special case: if any fragment has `structure_hint: "near_complete_demo"`,
set this component to 30 (a complete demo implies all sections present).

**Why this metric**: A project that has both a verse AND a chorus is much
closer to a finishable song than one with two verses and no chorus. A
project with no chorus candidates has more work ahead than one with a
chorus.

### Component 3: Emotional coherence (0-20 points)

Measures **how unified the project's emotional direction is**. A scattered
project (10 fragments with 8 different emotions) is hard to finish; a
focused project (10 fragments mostly converging on 2 emotions) has clear
direction.

```
all_emotions = list of every emotion tag across all fragments (with
              duplicates)

if len(all_emotions) == 0:
    return 10  # neutral; not penalized

unique_emotions = set(all_emotions)
dominant_count = count of the most-frequent emotion
total_count = len(all_emotions)
dominance_ratio = dominant_count / total_count

if dominance_ratio >= 0.6:
    coherence = 20  # very focused
elif dominance_ratio >= 0.4:
    coherence = 15  # focused
elif dominance_ratio >= 0.25:
    coherence = 10  # moderate
else:
    coherence = 5   # scattered
```

**Why this metric**: A project where 60% of emotion mentions are
`melancholy` has clear emotional direction. A project where 8 different
emotions each appear once has no center to write toward.

**Mixed emotions are not penalized in tag form**: A fragment tagged
`[melancholy, acceptance]` contributes 1 to melancholy and 1 to acceptance.
The pattern emerges across fragments.

### Component 4: Freshness (0-20 points)

Measures **whether the project is actively being worked on**.

```
days_since_last_activity = today - max(updated_at across fragments)

if days_since_last_activity <= 3:
    freshness = 20  # actively in progress
elif days_since_last_activity <= 14:
    freshness = 15  # recently active
elif days_since_last_activity <= 30:
    freshness = 10  # warm but quiet
elif days_since_last_activity <= 90:
    freshness = 5   # cooling off
else:
    freshness = 0   # dormant
```

**Why this metric**: A project the user just touched yesterday is highly
likely to be finished. A project untouched for 6 months is much less likely
to be revived — though Resurrect notifications can change this.

**Special case**: When Resurrect Notifier successfully reactivates a
dormant project (user added new material to it after dormancy), reset
freshness as if the activity is fresh.

## Tier mapping

After computing the score:

```
if rescue_score >= 70:
    tier = "high"
elif rescue_score >= 40:
    tier = "medium"
else:
    tier = "low"
```

**Tier guidance for Producer Agent**:

- **high tier**: Surface prominently. Suggest specific next actions.
  Encourage user to invest 30+ minutes.
- **medium tier**: Surface in lists. Suggest exploratory next actions.
  Encourage user to invest 15-20 minutes.
- **low tier**: Don't surface unprompted. When user views, suggest either:
  (a) "add 1-2 more fragments to make this finishable", or
  (b) "consider archiving — not all ideas need to become songs".

## Explanation generation

Produce a 1-2 sentence explanation tailored to the score. Examples:

**High score (78)**:
> "Strong project: verse and chorus material present, emotionally focused on
> melancholy and acceptance, and recently active. Good candidate for a
> finishing session."

**Medium score (52)**:
> "Moderate progress: 3 fragments with verse and lyric material, but no
> chorus candidate yet. A focused 30-minute session could move this forward
> significantly."

**Low score (28)**:
> "Sparse so far: 2 fragments, both lyric snippets without clear structure.
> Either expand with a melodic idea or set aside for now."

The explanation must:
- Reference specific facts (component scores) — don't be vague
- Use neutral language — don't say "weak song" or "great work"
- Suggest a next move when score is below 70

## Edge cases

### Project with 1 fragment
Set tier to `new` and don't compute the full score. Return:
```json
{
  "tier": "new",
  "rescue_score": null,
  "explanation": "Single-fragment project — needs at least one more idea to
                  evaluate."
}
```

### Project with no emotion tags at all
This is rare but possible (e.g., all fragments are pure instrumental
motifs without user descriptions). Set emotional_coherence to 10 (neutral)
and note this in the explanation:
> "Emotional direction unclear — most fragments are instrumental without
> descriptions. Adding user notes would help clarify the project's
> direction."

### Project marked as completed
If the user has explicitly marked the project as completed (a flag set in
the project document), do not compute or display Rescue Score. Show
"completed" status instead.

### Project marked as abandoned
If the user has explicitly archived the project, do not compute. Show
"archived" status.

### Project with conflicting structural hints
Example: 5 fragments all tagged `chorus_candidate`. This is technically
common (a songwriter exploring multiple chorus ideas), but structure_
completeness will only count it as 10 points.

This is correct behavior — the project doesn't have verse/bridge material
yet, so it's not closer to completion.

### Cross-mode contamination
Rescue Score should not consider Music Education Mode fragments mixed with
Creator Mode fragments. These have different goals. If a project somehow
contains both modes (data error), filter to a single mode before computing.

## What Rescue Score does NOT measure

To prevent misuse and miscommunication:

1. **It is NOT a song quality predictor.** A score of 30 doesn't mean the
   song is bad. Many great songs started at 30.

2. **It is NOT a commercial viability score.** It doesn't predict streaming
   numbers or audience reception.

3. **It is NOT a creativity score.** A user with 10 distinct, exploratory
   fragments might score lower than a user with 6 focused but predictable
   ones. That's fine — the score reflects *finishability*, not
   *interestingness*.

4. **It is NOT a competition.** Users should not feel judged by their score.
   Producer Agent must frame scores supportively, never as performance.

## Anti-gaming notes

A user might try to "increase" their score by:
- Adding many trivial fragments (richness goes up, but they're 4 points
  each)
- Tagging everything as the same emotion (coherence increases artificially)

The system is **not designed to be gameable** because the user has no
incentive to game it — the score is for *their own* awareness, not for
sharing or comparing. If users do appear to be gaming it, that's a signal
the score is being misused as a status indicator rather than a tool. The
Producer Agent should remind users in such cases that the score is for them.

## Versioning

If you change the formula (rebalance weights, add components), increment a
version number stored in `user_dna.rescue_score_version`. This allows the
Producer Agent to recompute scores when the formula changes and to inform
users that "this score reflects an updated formula" if needed.

Current version: **v1**.

## Sample calculations

### Example A: High-scoring project (78)
- 5 fragments, total text length 600 chars
  → richness = min(30, 5×4 + 600/100) = min(30, 26) = 26
- Has verse_candidate, chorus_candidate, lyric_fragment
  → structure = 10 + 10 = 20
- Emotions: 8 mentions of melancholy, 4 of acceptance, 2 of nostalgia
  (dominance = 8/14 = 0.57)
  → coherence = 15
- Last update: 5 days ago
  → freshness = 15

Total: 26 + 20 + 15 + 15 = **76**
Tier: high
Explanation: "Strong project: verse and chorus material with 5 fragments,
emotionally focused on melancholy and acceptance, recently active. Good
candidate for a finishing session."

### Example B: Medium-scoring project (52)
- 3 fragments, total text length 300 chars
  → richness = min(30, 12 + 3) = 15
- Has verse_candidate and lyric_fragment (no chorus)
  → structure = 10
- Emotions: 4 melancholy, 2 anxiety, 1 vulnerability (7 total, dominance
  4/7 = 0.57)
  → coherence = 15
- Last update: 20 days ago
  → freshness = 10

Total: 15 + 10 + 15 + 10 = **50**
Tier: medium
Explanation: "Moderate progress: 3 fragments with verse material but no
chorus yet. Adding a chorus candidate would significantly increase finishability."

### Example C: Low-scoring project (24)
- 2 fragments, total text length 50 chars
  → richness = min(30, 8 + 0.5) = 8
- Has lyric_fragment and melodic_motif (no major sections)
  → structure = 0
- Emotions: 1 sadness, 1 melancholy (2 total, dominance 1/2 = 0.5)
  → coherence = 15
- Last update: 100 days ago
  → freshness = 0

Total: 8 + 0 + 15 + 0 = **23**
Tier: low
Explanation: "Sparse so far: 2 small fragments, no structural sections,
dormant for 3+ months. Either expand with new material or consider
archiving."

### Example D: New project (no score)
- 1 fragment
- → score not computed
- Tier: new
- Explanation: "Single-fragment project — needs at least one more idea to
  evaluate."
