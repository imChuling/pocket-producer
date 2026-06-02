---
name: rescue-scoring
description: |
  Interpret and present the Rescue Score for a project — a 0-100 indicator
  of how likely the project is to be completed if the user invests more
  time. Used by Producer Agent to prioritize projects, generate next-action
  suggestions, and explain scores to users. The actual computation is in
  pure Python (backend/tools/rescue_score.py); this skill defines what the
  score means and how to communicate it.
license: Apache-2.0
---

# Rescue Scoring

Interpret the Rescue Score for a project — a 0–100 indicator of how likely
the project is to be completed into a finished song if the user invests
another 30–60 minutes. The score drives project ranking, surfacing,
next-action suggestions, and user-facing explanations.

This is **not a quality judgment**. A low score does not mean the song is
bad. It means the project has less material, less structural completeness,
less coherence, or less recent activity — making it harder to finish from
its current state.

The Rescue Score is the product's most visible numerical output. Users will
glance at it to decide where to spend their limited creative time.
Therefore: it must be **honest, stable, and explainable**.

## When to use this skill

Use this skill whenever:

1. A new fragment is added to a project — interpret the recomputed score.
2. A project hasn't been recomputed in 7+ days but is queried — trigger
   recomputation and interpret.
3. The user manually requests a score explanation.
4. Producer Agent needs to rank projects for surfacing to the user.
5. Producer Agent needs to generate a `next_action` suggestion for a
   project.

## When NOT to use this skill

- For individual fragments (fragments don't have Rescue Scores; only
  projects do)
- For new projects with 1 fragment (insufficient data — return
  `tier: "new"` with null score)
- For projects the user has explicitly marked as completed or archived
- When the question is about fragment tagging (use `music-tagging`) or
  relationships (use `relationship-rules`)

## Input

You receive a project document with its computed score and member
fragments:

```json
{
  "project_id": "string",
  "title": "Rain Song",
  "fragment_count": 5,
  "fragments": [
    {
      "fragment_id": "string",
      "raw_text": "string | null",
      "text": "string | null",
      "emotions": ["melancholy", "acceptance"],
      "structure_hint": "verse_candidate",
      "style": ["singer-songwriter"],
      "updated_at": "ISODate"
    }
  ],
  "rescue_score": 76,
  "score_breakdown": {
    "richness": 26,
    "structure_completeness": 20,
    "emotional_coherence": 15,
    "freshness": 15
  },
  "status": "active | completed | archived"
}
```

The numeric score and component breakdown are **already computed** by
`backend/tools/rescue_score.py`. Your job is to interpret, explain, and
suggest next actions — not to recalculate.

If `status` is `completed` or `archived`, do not interpret — return the
appropriate status label instead.

## Output schema

```json
{
  "project_id": "string",
  "rescue_score": 76,
  "components": {
    "richness": 26,
    "structure_completeness": 20,
    "emotional_coherence": 15,
    "freshness": 15
  },
  "tier": "high | medium | low | new",
  "explanation": "string",
  "next_action": {
    "action": "string",
    "estimated_time": "string",
    "why": "string"
  },
  "weakest_component": "string | null"
}
```

### Field meanings

- `rescue_score`: integer 0-100. Computed by Python, passed through.
- `components`: each component's contribution (passed through from
  computation).
- `tier`: see "Tier mapping" below.
- `explanation`: a 1-2 sentence human-readable summary for the user.
  This is **the most important field you produce** — see "Explanation
  generation" below.
- `next_action`: a concrete, actionable suggestion the user can execute
  in one session. See "Next-action generation" below.
- `weakest_component`: which component is holding the score back most.
  `null` only for `new` tier.

## Procedure

### Step 1: Validate input

- If `fragment_count < 2`, return `tier: "new"` with `rescue_score: null`
- If `status` is `completed` or `archived`, return that status
- Otherwise proceed

### Step 2: Assign tier

Apply the tier mapping below.

### Step 3: Identify the weakest component

Find which component is furthest below its maximum as a percentage:
- richness: max 30
- structure_completeness: max 30
- emotional_coherence: max 20
- freshness: max 20

The component with the lowest percentage of its max is the `weakest_
component`. This drives the next-action suggestion.

### Step 4: Generate next_action

Based on `weakest_component` and tier, select the most impactful
concrete action the user can take. See "Next-action generation" below.

### Step 5: Generate explanation

Write a 1-2 sentence explanation. See "Explanation generation" below.

### Step 6: Return result

Assemble the full output JSON.

---

## Formula reference (computed by Python)

The actual computation lives in `backend/tools/rescue_score.py`. This
section is a **brief reference** so you understand what the numbers mean.
You do not need to perform these calculations.

```
rescue_score = richness + structure_completeness
             + emotional_coherence + freshness
```

| Component | Max | What it measures | Key formula |
|---|---|---|---|
| **Richness** | 30 | Amount of raw material | `min(30, count × 4 + text_len / 100)` |
| **Structure** | 30 | Distinct song sections present | +10 verse, +10 chorus, +5 hook, +5 bridge (cap 30) |
| **Coherence** | 20 | Emotional focus/direction | Based on dominant emotion ratio (≥0.6→20, ≥0.4→15, ≥0.25→10, else→5) |
| **Freshness** | 20 | Recency of activity | ≤3 days→20, ≤14→15, ≤30→10, ≤90→5, else→0 |

Special cases handled by Python:
- `near_complete_demo` structure hint → structure = 30
- No emotion tags at all → coherence = 10 (neutral)
- Single fragment → score not computed (`new` tier)

---

## Tier mapping

| Score | Tier | User-facing meaning |
|---|---|---|
| 70–100 | `high` | Good candidate for a finishing session |
| 40–69 | `medium` | Needs focused work to move forward |
| 0–39 | `low` | Sparse or dormant — expand or archive |
| n/a | `new` | Single fragment, needs more material |

---

## Next-action generation

This is the Producer Agent's most valuable output. A good next_action is:
- **Concrete**: "Record a vocal melody over the Am piano motif" not
  "work on the project more"
- **Time-bounded**: always include `estimated_time` ("15 min", "30 min")
- **Targeted at the weakest component**: fix what's holding the score back
- **Musically specific when possible**: reference the project's actual
  key, BPM, emotions, and fragment content

### Actions by weakest component

#### When richness is weakest (score < 15/30)

The project lacks raw material. The user needs to **add more fragments**.

| Situation | Suggested action | Est. time |
|---|---|---|
| Only 2 fragments, both text | "Record a voice memo — hum or sing one of these lyrics to capture the melody in your head" | 10 min |
| Only text fragments, no audio | "Record a rough instrumental sketch — even 15 seconds of piano or guitar would anchor the mood" | 15 min |
| Only audio, no text | "Write down the lyrics or describe what each fragment means to you — text helps find connections" | 10 min |
| Fragments are very short (< 50 chars each) | "Expand one of your fragments — add a second line, a rhyme, or describe the image more specifically" | 15 min |
| Moderate fragments but thin text | "Pick your strongest fragment and develop it — add a second verse or extend the imagery" | 20 min |

#### When structure is weakest (score < 15/30)

The project has material but no clear song sections.

| Missing section | Suggested action | Est. time |
|---|---|---|
| No verse_candidate | "Try writing a verse that tells the story behind [reference strongest emotion or theme]" | 20 min |
| No chorus_candidate | "Write a chorus — a repeatable, emotionally concentrated version of [project's core theme]" | 20 min |
| Has verse + chorus but no hook | "Distill your chorus into a single memorable phrase — the line someone would hum after hearing the song" | 15 min |
| Has verse + chorus but no bridge | "Write a bridge that shifts perspective — say the same thing differently, or reveal something new" | 20 min |
| All fragments are the same section type | "You have [N] [section type] ideas — try writing a contrasting section (if all verses, try a chorus; if all hooks, try a verse)" | 20 min |

#### When coherence is weakest (score < 10/20)

The project's emotional direction is scattered.

| Situation | Suggested action | Est. time |
|---|---|---|
| 4+ different emotions, no dominant | "Listen to all your fragments back-to-back. Which emotional thread feels strongest? Record a new fragment that doubles down on that feeling" | 20 min |
| Two competing emotional directions | "This project pulls between [emotion A] and [emotion B]. That tension could be the song's core — try writing a bridge that connects them" | 25 min |
| Emotions conflict without intent | "Some fragments feel [emotion A] while others feel [emotion B]. Consider splitting this into two projects, each with a clearer emotional center" | 15 min |

#### When freshness is weakest (score < 10/20)

The project is dormant — the user hasn't touched it recently.

| Days since activity | Suggested action | Est. time |
|---|---|---|
| 30–90 days | "It's been a while since you worked on '[project title]'. Listen back to what you have — does it still resonate? If yes, add one new fragment to pick up the thread" | 15 min |
| 90+ days | "This project has been sleeping for [N] months. Sometimes distance creates perspective — listen back and decide: revive it with fresh material, or archive it and free the mental space" | 10 min |
| Resurrect notification triggered | "A new fragment you recorded recently sounds like it could belong with '[project title]' — listen to both and see if the connection feels right" | 10 min |

### Making next_action musically specific

Whenever possible, reference actual project data:

**Generic** (avoid): "Add more material to the project"

**Specific** (prefer): "Record a vocal melody over the Am piano motif at
72 BPM — your hook lyric 'the rain is me' needs a melodic shape"

To generate specific actions, use:
- The project's dominant key and BPM (from fragment audio_features)
- The strongest emotion tags (what the song is "about")
- Actual lyric quotes from fragments (make the suggestion feel personal)
- The missing structural section (what would make it more complete)
- The project's style tags (suggest actions consistent with the genre)

---

## Explanation generation

The `explanation` field is shown directly to users. It must:

1. **Name what's strong** — always start with what the project HAS
2. **Name the gap** — what's holding the score back
3. **Suggest the move** — point toward the next_action
4. **Use neutral, supportive language** — never judge quality

### Templates by tier

**High tier (70-100):**

Pattern: "[Strength]. [Minor gap if any]. [Encouragement]."

Examples:
- "Strong project: verse and chorus material in Am, emotionally focused
  on melancholy and acceptance, and recently active. A 30-minute session
  could get this to demo stage."
- "Nearly complete: 6 fragments covering verse, chorus, and hook, with
  a consistent longing feel. The main gap is the bridge — one more
  contrasting section would tie it together."
- "Well-developed: rich material with clear structure and emotional
  coherence. Fresh activity suggests you're in the zone — keep going."

**Medium tier (40-69):**

Pattern: "[What exists]. [What's missing]. [Specific suggestion]."

Examples:
- "Good foundation: 3 fragments with verse material and a focused
  melancholy feel, but no chorus candidate yet. A focused 30-minute
  session on a chorus could move this significantly."
- "Promising material: emotionally coherent and structurally varied,
  but only 2 fragments — adding more raw material would give you more
  to work with."
- "Interesting start: 4 fragments with diverse ideas, but the emotional
  direction is scattered across anger, hope, and anxiety. Picking one
  thread to follow would help this coalesce."

**Low tier (0-39):**

Pattern: "[What's there]. [Why it's early]. [Two options: expand or archive]."

Examples:
- "Early stage: 2 short fragments, no clear structure yet, and dormant
  for 3 months. Either expand with a melodic idea or set aside for now
  — not all seeds need to grow right away."
- "Sparse so far: a lyric snippet and a melodic motif, but no structural
  sections and mixed emotions. A focused session adding a verse or chorus
  would give this shape."
- "Dormant: 3 fragments from 6 months ago with no recent activity. Listen
  back — if the spark is still there, a single new fragment can revive it."

**New tier:**

Always the same pattern:
- "Single-fragment project — needs at least one more idea before I can
  suggest next steps."

### Language rules

| DO | DON'T |
|---|---|
| "Early stage" | "Weak" or "poor" |
| "Sparse so far" | "Not enough" or "insufficient" |
| "Needs focused work" | "Needs a lot of work" |
| "Dormant" or "sleeping" | "Abandoned" or "forgotten" |
| "Set aside for now" | "Give up on this" |
| "Emotionally scattered" | "Confused" or "incoherent" |
| Reference specific fragments | Use abstract component names |
| "A 30-minute session could..." | "You should..." or "You need to..." |

### Score change narratives

When a fragment is added and the score changes, explain the delta:

**Score went up:**
- "Adding that [structure_hint] fragment in [key] bumped the score from
  [old] to [new] — the project now has [what improved]."
- Example: "Adding that chorus candidate in Am bumped the score from 45
  to 62 — the project now has both verse and chorus material."

**Score went down (rare — usually from freshness decay):**
- "The score dropped from [old] to [new] because [component] changed —
  [explanation]."
- Example: "The score dropped from 65 to 55 because it's been 3 weeks
  since the last update. Adding new material would restore the freshness
  boost."

**Score unchanged after adding a fragment:**
- "The new fragment adds material but the score stays at [N] because
  [what's still missing]."
- Example: "The new fragment adds material but the score stays at 48
  because the project still needs a chorus — that's the biggest gap."

---

## Presentation context

How to present scores depends on WHERE the user encounters them.

### Project list view

The user is scanning multiple projects to decide where to invest time.

- Show: score number, tier badge, project title, one-line explanation
- Prioritize: sort by score descending (high-tier projects first)
- For `new` tier: show "needs more material" instead of a number
- Never show component breakdowns in list view — too much detail

### Single project view

The user is looking at one project in detail.

- Show: score number, tier badge, full explanation, component breakdown
  (as a visual — bars or percentages, not raw numbers), next_action
- Highlight the weakest component visually
- Show score history if available (did it go up or down recently?)

### Notification context (Resurrect)

The user receives a notification about a dormant project.

- Lead with the connection ("A new idea you recorded sounds like it
  belongs with '[project title]'")
- Mention the score only as context ("That project scored [N] — a
  focused session could revive it")
- Focus on the action, not the number

### Conversation context (Producer Agent responding)

When the Producer Agent talks about a project inline:

- Never lead with the number ("Your project scored 52" is bad)
- Lead with the insight ("Your 'Rain Song' project has a verse and a
  hook but no chorus — that's the biggest gap")
- Mention the score only if the user asks or if comparing projects

---

## Edge cases

### Project with 1 fragment
Return `tier: "new"`, `rescue_score: null`, no next_action.
Explanation: "Single-fragment project — needs at least one more idea to
evaluate."

### Project with no emotion tags at all
Set coherence to 10 (neutral, not penalized). Explanation should note:
"Emotional direction unclear — most fragments are instrumental without
descriptions. Adding notes about the mood would help clarify direction."

### Project marked as completed or archived
Do not compute or display score. Show status label only.

### All fragments have the same structure_hint
Common case: 5 fragments all tagged `chorus_candidate`. Structure
completeness counts only unique section types, so this scores 10/30.
This is correct — the project is chorus-heavy but lacks verse/bridge.
The next_action should suggest the missing section type.

### Score goes down after adding a fragment
This can happen if:
- The new fragment introduces a conflicting emotion (coherence drops)
- Freshness was already high and the new fragment doesn't change it

Do NOT apologize or frame this negatively. Explain what changed:
"The new fragment introduced [emotion] alongside the project's existing
[dominant emotion] — the emotional direction is a bit more scattered now.
That's not a bad thing if the contrast is intentional."

### Very high score (90+)
Rare but possible. Don't oversell it:
"This project is well-developed across all dimensions — material, structure,
emotional focus, and momentum. It's ready for a finishing session whenever
you are."

### Cross-mode contamination
If a project contains Music Education Mode fragments mixed with Creator
Mode fragments, filter to a single mode before interpreting. These have
different goals.

---

## What Rescue Score does NOT measure

Present these boundaries clearly when users ask or seem confused:

1. **It is NOT a song quality predictor.** A score of 23 doesn't mean the
   song is bad. Many iconic songs started as 2 sparse fragments. The
   score measures *finishability from current state*, not *potential*.

2. **It is NOT a commercial viability score.** It doesn't predict
   streaming numbers, audience reception, or market fit.

3. **It is NOT a creativity score.** A user with 10 distinct, exploratory
   fragments might score lower than a user with 6 focused but predictable
   ones. That's fine — the score reflects *how close to completion*, not
   *how interesting*.

4. **It is NOT a competition.** Users should never feel judged. The
   Producer Agent must frame scores supportively, never as performance
   metrics. Never compare one user's scores to another's.

If a user says something like "my score is only 35, I suck at this",
the correct response is: "A score of 35 means the project is early —
it needs more material and structure to be finishable. It says nothing
about whether the ideas are good. Some of the best songs take the longest
to assemble."

---

## Anti-gaming notes

If a user appears to be gaming the score (adding trivial fragments,
force-tagging emotions), remind them:
- "The score is for your own awareness, not a metric to optimize"
- "Adding empty fragments raises richness slightly but doesn't make the
  song more finishable"
- The score has natural diminishing returns (richness caps at 30, coherence
  rewards focus not quantity)

---

## Versioning

Current formula version: **v1**.

If the formula changes (rebalance weights, add components), increment a
version in `user_dna.rescue_score_version`. The Producer Agent should
recompute and note: "this score reflects an updated formula."

---

## Worked examples

### Example A: High-tier project — generate next_action

Input:
- "Rain Song", 5 fragments, 600 chars total text
- Score: 76 (richness 26, structure 20, coherence 15, freshness 15)
- Has verse_candidate, chorus_candidate, lyric_fragment
- Emotions: melancholy ×8, acceptance ×4, nostalgia ×2
- Dominant key: Am, dominant BPM: 72
- Last activity: 5 days ago

Interpretation:
- Tier: `high`
- Weakest component: coherence (15/20 = 75%) — but this is not bad.
  Structure (20/30 = 67%) is actually the weakest by percentage.
- Missing: hook_candidate and bridge_candidate would reach 30/30 structure
- next_action: "Write a bridge that shifts away from the rain imagery —
  maybe what comes after the rain stops. Am at 72 BPM, 20-30 seconds.
  This would complete the song's structure." (est. 20 min)
- Explanation: "Strong project: verse and chorus in Am at 72 BPM,
  emotionally focused on melancholy and acceptance. A bridge section would
  round out the structure — the song has a clear shape already."

### Example B: Medium-tier project — structure is the gap

Input:
- "Streetlight", 3 fragments, 300 chars total text
- Score: 50 (richness 15, structure 10, coherence 15, freshness 10)
- Has verse_candidate only
- Emotions: longing ×4, melancholy ×2, hope ×1
- Last activity: 20 days ago

Interpretation:
- Tier: `medium`
- Weakest component: structure (10/30 = 33%)
- Missing: chorus_candidate (biggest impact on structure)
- next_action: "Your verse explores longing beautifully — now write the
  chorus. What's the one thing you want the listener to feel most? Distill
  that into 2-4 repeatable lines." (est. 20 min)
- Explanation: "Promising material: 3 fragments with a focused longing
  feel and verse material, but no chorus yet. Writing a chorus is the
  single biggest move to push this forward."

### Example C: Low-tier project — dormant and sparse

Input:
- "Untitled", 2 fragments, 50 chars total text
- Score: 23 (richness 8, structure 0, coherence 15, freshness 0)
- Has lyric_fragment and melodic_motif only
- Emotions: sadness ×1, melancholy ×1
- Last activity: 100 days ago

Interpretation:
- Tier: `low`
- Weakest component: freshness (0/20 = 0%) and structure (0/30 = 0%)
  — tie, but freshness is the blocker because the user isn't engaged.
- next_action: "It's been 3 months since you touched this. Listen back
  to your two fragments — if the sadness still resonates, record a verse
  that tells the story behind the feeling. If not, consider archiving."
  (est. 15 min)
- Explanation: "Early stage: 2 short fragments, no structure, dormant
  for 3 months. Listen back — if the spark is still there, one focused
  session could give this shape."

### Example D: New project

Input:
- 1 fragment

Output:
- Tier: `new`, rescue_score: null
- next_action: null
- Explanation: "Single-fragment project — needs at least one more idea
  before I can suggest next steps."

### Example E: Score change after adding a fragment

Before: "Quiet Hours", score 45 (richness 12, structure 10, coherence 15,
freshness 8)
User adds: a chorus_candidate fragment with emotion [melancholy]
After: score 67 (richness 18, structure 20, coherence 17, freshness 20)

Score change narrative: "That chorus fragment jumped the score from 45
to 67 — the project now has both verse and chorus material, and the new
fragment reinforced the melancholy focus. The biggest remaining gap is
richness — a few more fragments would round this out."

### Example F: High coherence but user adds a conflicting fragment

Before: "Midnight", score 62 (richness 20, structure 20, coherence 20,
freshness 2)
User adds: a fragment with emotion [joy, excitement] (everything else was
melancholy)
After: score 63 (richness 24, structure 20, coherence 10, freshness 20)

Coherence dropped from 20 to 10, but richness and freshness rose.

Score change narrative: "The new fragment revived the project's momentum
(freshness jumped from 2 to 20) and added material, but it introduced
joy into a project that was consistently melancholy. The emotional
direction is now more scattered — if the contrast between joy and
melancholy is intentional, that's a powerful artistic choice. If not,
you might consider splitting this fragment into a separate project."

---

## Common mistakes

1. **Leading with the number.** "Your project scored 52" is impersonal.
   Lead with the insight: "Your 'Rain Song' has a verse and a hook but
   no chorus — that's the biggest gap."

2. **Treating Rescue Score as a quality judgment.** A score of 23 does
   not mean the song is bad. Frame it as finishability, not quality.

3. **Generating vague next_actions.** "Work on the project more" is
   useless. Always reference specific fragments, keys, emotions, or
   missing sections.

4. **Presenting component scores as raw numbers.** "Richness: 8" means
   nothing. Say: "only 2 short fragments — adding more material would
   help."

5. **Ignoring the `new` tier.** A project with 1 fragment should NOT get
   a numeric score or a next_action. The formula needs at least 2
   fragments.

6. **Recomputing unnecessarily.** If nothing changed and fewer than 7
   days passed, the previous score is still valid.

7. **Apologizing for low scores.** Don't say "unfortunately your score
   is low." Say "this project is early — here's what would move it
   forward."

8. **Comparing users' scores.** Never. The score is personal, not
   competitive.
