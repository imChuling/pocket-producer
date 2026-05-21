# Theme Taxonomy

Themes describe **what a fragment is about** — the subject matter, not the
feeling. A song about loss can feel like peace; a song about a sunset can
feel like fear. Themes and emotions are independent.

Themes are noun-phrase topics. Use this taxonomy to pick 1-3 theme tags.
Empty `theme: []` is acceptable when the fragment has no discernible subject
(common for pure instrumental fragments and abstract emoji input).

## The 24 theme categories

Themes are grouped into 6 clusters. Within each cluster, the tags are
distinct enough to be used as separate filters.

### Cluster 1: Self and identity

#### `self-identity`
The fragment is about who the speaker is, how they see themselves, or how
they've changed.
- Markers: "I am", "I used to be", "I'm becoming", "Who am I"
- Examples: "I'm not the person you remember"

#### `self-doubt`
Specifically about questioning one's worth, choices, or ability.
- Markers: "Am I", "What if I'm wrong", "I don't know how", self-deprecation
- Examples: "Maybe I was never any good at this"

#### `mental-health`
Explicit references to depression, anxiety, addiction, recovery, or other
mental health states. Use this when the fragment treats mental health as
the subject, not just as the emotion behind another subject.
- Markers: explicit terms ("anxious", "depressed"), therapy references
- Examples: "I count my breaths in the morning"

### Cluster 2: Relationships

#### `love-romantic`
Romantic love, current or potential. Use this when the relationship is
present-tense and unambiguous.
- Markers: declarations, present-tense affection, sensual specifics
- Examples: "You make every room warmer"

#### `heartbreak`
Specifically about the end of a romantic relationship or its aftermath.
- Markers: "we're done", past tense for a "we", grief over a person
- Examples: "I keep buying coffee for two"

#### `unrequited`
Wanting someone who doesn't want you (or doesn't know).
- Markers: longing without reciprocation, secrecy of feeling
- Examples: "You don't even know my name"

#### `family`
Parents, children, siblings, chosen family. Any non-romantic family
relationship.
- Markers: specific family terms ("mother", "brother"), inheritance imagery
- Examples: "My father's hands looked like mine today"

#### `friendship`
Non-romantic friendship — its joys, betrayals, distances.
- Markers: shared history, names, plural pronouns about peers
- Examples: "We're not who we were that summer"

#### `solitude`
Being alone — whether by choice, circumstance, or imposition. Distinct from
loneliness emotion (which is about *feeling* alone).
- Markers: spatial descriptions of one person, no other characters
- Examples: "My apartment learns my footsteps"

### Cluster 3: Time and memory

#### `nostalgia-memory`
A specific past memory is the subject. The fragment is *about* remembering.
Distinct from `nostalgia` emotion which is the *feeling* of remembering.
- Markers: specific dates/places/people from the past, sensory recall
- Examples: "The pool smelled like summer 1998"

#### `aging`
Time's passage, getting older, changes that came with time.
- Markers: birthdays, gray hair, body changes, generational references
- Examples: "I never thought I'd say 'when I was young'"

#### `mortality`
Death, dying, the awareness of finitude. Either someone else's death or one's
own awareness.
- Markers: funeral imagery, last words, hospice, "before I"
- Examples: "Mom's hands got smaller this year"

#### `time-passage`
The general feeling of time moving — distinct from aging (specifically about
self) and mortality (specifically about death). About time itself.
- Markers: seasons, days/weeks/years passing, repetition over time
- Examples: "Another Tuesday in a Tuesday in a Tuesday"

### Cluster 4: Place and belonging

#### `home`
A specific place that is or was home. Houses, rooms, streets.
- Markers: address references, room descriptions, "where I grew up"
- Examples: "The kitchen tile remembered my knees"

#### `hometown`
Specifically the place of origin, distinct from current home. About leaving,
returning, or being from somewhere.
- Markers: city/town names, "back home", "I'm from"
- Examples: "Albany feels smaller than it used to"

#### `displacement`
Being away from home, immigration, exile, refugee experience. Distance from
where one belongs.
- Markers: distance imagery, two-place comparisons, language mixing
- Examples: "Two passports, one tongue"

#### `nature`
The natural world as the primary subject. Not just a setting but a subject.
- Markers: ecosystems, weather as theme, animals, plants
- Examples: "The river kept its own time"

### Cluster 5: Inner life

#### `dreams`
Literal dreams, sleep, the dreamlife. Or the metaphorical sense of dreaming
about possible futures.
- Markers: sleep states, "I dreamt", surreal imagery
- Examples: "Last night I built a house from old letters"

#### `faith-doubt`
Religion, spirituality, the loss or finding of faith. Either positive or
critical.
- Markers: religious vocabulary, prayer imagery, theological questioning
- Examples: "I keep talking to someone who doesn't answer"

#### `purpose-meaning`
Searching for or questioning life's purpose. Larger existential questions.
- Markers: "what's it for", "why am I", purpose-talk
- Examples: "Forty-three and still not what I meant to be"

#### `freedom-escape`
Wanting to leave, getting away, breaking free. The active desire to escape.
- Markers: leaving imagery, open roads, doors, breaking
- Examples: "If I just got in the car right now"

### Cluster 6: World and politics

#### `social-critique`
The fragment comments on society, systems, injustice, or political reality.
- Markers: collective pronouns ("we", "they") about systems, named issues
- Examples: "The whole machine is older than my grandfather"

#### `current-events`
Specific recent events — wars, elections, disasters, public moments.
- Markers: named events, dates close to writing, news vocabulary
- Examples: "We watched the city burn on our phones"

#### `class-money`
Economic life — work, money, class. Both the absence and presence of
resources.
- Markers: dollars, jobs, bills, hours, paychecks
- Examples: "I priced the rent against the rest of my life"

## Decision flowchart

For each fragment, walk through these questions:

**Q1: Is the subject matter clear from the fragment?**

If yes → Pick 1-2 theme tags. Stop.
If no (e.g., pure instrumental, abstract lyric) → Go to Q2.

**Q2: Is there any subject reference at all?**

If yes (e.g., a place name, a relationship word, a season) → Pick 1 tentative
tag and note in reasoning.

If no → Leave `theme: []`. This is normal for instrumental fragments and
many emoji inputs.

**Q3: Are multiple themes present?**

Many strong fragments span 2 themes. Common pairings:
- `heartbreak` + `home` (lost partner, empty house)
- `aging` + `family` (parents getting older)
- `self-doubt` + `purpose-meaning` (existential questioning)
- `hometown` + `displacement` (immigrant experience)
- `friendship` + `nostalgia-memory` (old friends, old times)

Pick the **stronger** theme first, then the secondary. Max 3 tags but usually
2 is plenty.

## Distinctions that often confuse the model

### `nostalgia-memory` (theme) vs `nostalgia` (emotion)
- Theme = the fragment is *about* a memory
- Emotion = the fragment *feels* nostalgic

A fragment can have nostalgic feeling without being about memory ("Sundays
in October always sound like this") → `nostalgia` emotion, theme might be
`time-passage` or empty.

A fragment can be about a memory without feeling nostalgic ("I remember the
exact moment I knew I had to leave him") → theme `nostalgia-memory` or
`heartbreak`, emotion might be `defiance` or `acceptance`.

### `solitude` vs `loneliness` (emotion)
- `solitude` is the situation (being alone)
- `loneliness` is the feeling about it (which can be present or not)

A fragment can describe solitude with peace ("My apartment, my coffee, my
morning") → theme `solitude`, emotion `peacefulness`.

A fragment can describe being in a crowd while feeling lonely → no `solitude`
theme; emotion `loneliness`.

### `home` vs `hometown`
- `home` = where you live or lived (a specific dwelling)
- `hometown` = where you're from (a place of origin/identity)

These can overlap but often don't.

### `love-romantic` vs `heartbreak`
- `love-romantic` is present-tense, alive
- `heartbreak` is past-tense or in-the-ending

A song saying "I miss you" → `heartbreak`, not `love-romantic`.
A song saying "I love you and I'm scared you'll leave" → `love-romantic` +
possibly `anxiety` emotion.

### `mental-health` vs emotion tags
- Use `mental-health` as theme **only when mental health is the subject**
- A sad song is not automatically `mental-health` themed

"I miss you" → emotion `sadness` or `loss`. Not `mental-health` themed.
"I tracked every meal this week" → `mental-health` themed.
"My therapist asked me about my mother" → `mental-health` + `family` themed.

## What is NOT a theme

These are common requests that should NOT be theme tags:

- **Emotions** — those go in `emotion`. "Sadness" is not a theme.
- **Adjectives** — "dark", "intimate", "epic". These describe style/feeling.
- **Genres** — "indie folk", "trap". Those go in `style`.
- **Sounds** — "piano", "808s", "acoustic guitar". Production talk, not theme.
- **Speeds** — "slow song", "ballad". This goes in `style` or structure.
- **Generic placeholders** — "life", "feelings", "thoughts". Too vague to
  be useful for retrieval.

If a fragment really has no theme — leave the array empty. Empty is
acceptable and often correct.

## When to leave theme empty

- Pure instrumental motifs with no user description
- Single emojis without strong topical association
- Very short fragments (single word, single chord progression)
- Abstract sound experiments with no narrative content

These are common cases. An empty `theme` array is not a refusal — it's an
honest signal that the fragment is purely sonic. Other agents will respect
this and not pretend the fragment is "about" something.
