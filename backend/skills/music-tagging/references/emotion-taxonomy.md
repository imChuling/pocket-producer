# Emotion Taxonomy

This taxonomy is used by the Gemini tagging pipeline to assign emotion tags to fragments.
It is based on the **Geneva Emotional Music Scale (GEMS)** (Zentner, Grandjean
& Scherer, 2008), a peer-reviewed framework specifically developed for music-
induced emotions, and extended with practical tags songwriters use day-to-day.

GEMS was chosen over alternatives (Russell circumplex, Plutchik wheel, Ekman
basic emotions) because it was designed for **music**, not faces or general
affect. The original GEMS-9 categories are: wonder, transcendence, tenderness,
nostalgia, peacefulness, power, joyful activation, tension, sadness.

We retain GEMS-9 as the spine and add 11 commonly-used tags that songwriters
actually use, giving 20 total. Each tag is precise enough to be distinguishable
from its neighbors but broad enough to apply to many fragments.

## The 20 emotion tags

### GEMS core (9 tags)

#### `wonder`
A sense of awe, marvel, or being captivated by something larger than oneself.
- Examples: "Look at the stars / I've never seen them all at once"
- Audio hints: ascending melodies, sustained open chords, sparse arrangement
- Common in: opening lines, bridge sections, ambient textures
- Often pairs with: `peacefulness`, `tenderness`

#### `transcendence`
A feeling of moving beyond the self — spiritual elevation, ego dissolution,
sublime experience. Distinct from wonder by being more inward.
- Examples: "I'm not anyone anymore", "Carry me out of myself"
- Audio hints: long sustained notes, modal harmony (Lydian, Phrygian)
- Common in: bridges, outros, climactic moments
- Often pairs with: `wonder`, `acceptance`

#### `tenderness`
Soft warmth, care, vulnerability shared. Affection without being romantic.
- Examples: "Sleep, little one", "I'll wait, I have time"
- Audio hints: slow tempo, intimate dynamics, finger-picked guitar
- Common in: lullabies, songs to family, gentle confessions
- Often pairs with: `melancholy`, `acceptance`, `nostalgia`

#### `nostalgia`
Bittersweet longing for the past. Specifically about *what is gone*. Not just
sadness — there is sweetness in the memory.
- Examples: "Remember that summer we...", "I drove past the old house"
- Audio hints: any tempo; lyrically marked by past tense and specific imagery
- Common in: verses recalling specific memories
- Often pairs with: `tenderness`, `melancholy`, `acceptance`

#### `peacefulness`
Calm, stillness, contentment, absence of struggle. Distinct from joy by being
quieter and from acceptance by being less hard-won.
- Examples: "Morning light through the curtain", "Nothing left to fix"
- Audio hints: slow BPM (< 80), major or modal harmony, low dynamic range
- Common in: opening verses, outros, contemplative bridges
- Often pairs with: `tenderness`, `wonder`

#### `power`
Strength, confidence, command, agency. Not aggression — power *without*
needing to fight.
- Examples: "I built this room with my own hands", "Watch me"
- Audio hints: strong rhythmic feel, full arrangement, sustained vowels
- Common in: choruses, statements of identity
- Often pairs with: `defiance`, `joy`

#### `joyful_activation`
Energetic happiness, exhilaration, dancing-on-the-spot feeling. Full-body joy,
not gentle.
- Examples: "I could do this all night", upbeat dance hooks
- Audio hints: fast BPM (> 120), major key, syncopated rhythms
- Common in: choruses, hooks, dance tracks
- Often pairs with: `power`, `playfulness`

#### `tension`
Unresolved anxiety, suspense, unease. Something is building or pressing.
Distinct from anxiety (below) by being more about *anticipation* than fear.
- Examples: "Something's about to break", staccato repeated notes
- Audio hints: minor key, dissonant intervals, building dynamics, ostinato
- Common in: pre-choruses, bridges that precede a chorus drop
- Often pairs with: `anxiety`, `defiance`

#### `sadness`
A core sad feeling. Use this when sadness is *present and acknowledged*, not
hidden or transformed.
- Examples: "I miss you and I can say it now"
- Audio hints: minor key, slow-mid tempo, descending melodic contour
- Common in: any section
- Often pairs with: `loneliness`, `loss`, `melancholy`

### Extended set (11 tags)

#### `melancholy`
A *thoughtful*, reflective sadness. Distinct from `sadness` by having more
cognitive depth — not just feeling sad, but *thinking about* sadness.
- Examples: "I keep waiting for the rain to stop, but the rain is me"
- Audio hints: minor key with extensions (m7, m9), slow tempo, sparse texture
- This is the most common emotion tag in singer-songwriter material
- Often pairs with: `nostalgia`, `acceptance`, `loneliness`

#### `acceptance`
Coming to terms with something difficult. Pain that has been processed. The
emotional space *after* grief, not during it.
- Examples: "I won't fight the morning anymore"
- Audio hints: resolved harmony (return to tonic), settled tempo
- Common in: final choruses, outros, second halves of bridges
- Often pairs with: `melancholy`, `peacefulness`

#### `longing`
Wanting something or someone that is absent. The emotional pull *toward*
something out of reach. Distinct from `nostalgia` (past) and `desire` (future).
- Examples: "If I could just hear your voice once"
- Audio hints: rising melodic phrases, suspended chords, unresolved cadences
- Common in: verses, pre-choruses
- Often pairs with: `melancholy`, `tenderness`

#### `loneliness`
The specific feeling of being alone, separated, unwitnessed. A spatial-
emotional sense.
- Examples: "The streetlight is the only thing watching me"
- Audio hints: sparse arrangement, single instrument and voice
- Common in: verses
- Often pairs with: `melancholy`, `sadness`

#### `loss`
The specific emotional state of having lost something or someone. More
concrete than sadness; carries an object.
- Examples: "Your chair is still warm and you're already gone"
- Audio hints: descending bass lines, minor key, slow tempo
- Common in: verses, especially narrative songs about grief
- Often pairs with: `sadness`, `melancholy`, `tenderness`

#### `anxiety`
Fear-based unease. Specifically about *what might happen*. Distinct from
`tension` (anticipation, often pleasant) by being unpleasant and fear-driven.
- Examples: "I keep checking my phone", "What if she doesn't come back"
- Audio hints: repetitive rhythmic patterns, minor key, urgent tempo
- Common in: verses, pre-choruses
- Often pairs with: `tension`, `vulnerability`

#### `vulnerability`
The state of being emotionally exposed. Distinct from sadness by being more
about *self-revelation* than the underlying feeling itself.
- Examples: "Here's what I haven't told anyone yet"
- Audio hints: intimate dynamics, single instrument, quiet vocal delivery
- Common in: pre-choruses, bridges, confessional verses
- Often pairs with: `tenderness`, `melancholy`

#### `defiance`
Willful resistance, refusal to give in. Not anger — more controlled and
purposeful. The "fuck you" with a smile.
- Examples: "Tell me one more time I can't"
- Audio hints: strong backbeat, sustained vocal power, repeated phrases
- Common in: choruses, hooks
- Often pairs with: `power`, `anger`

#### `anger`
Hot, present anger. Not bitterness (cold) or defiance (controlled).
- Examples: "I'm done being polite"
- Audio hints: aggressive dynamics, sharp consonants, distorted instruments
- Common in: bridges, hooks of confrontational songs
- Often pairs with: `defiance`, `tension`

#### `playfulness`
Light, mischievous, fun energy. Not as deep as joy; more about flirtation
with feeling.
- Examples: "Maybe I should, maybe I shouldn't"
- Audio hints: bouncy rhythm, major key, ascending lines
- Common in: verses, hooks of pop songs
- Often pairs with: `joyful_activation`

#### `desire`
Wanting (toward someone or something), especially romantic or sensual longing
oriented to the future. Distinct from `longing` (something absent) by being
forward-looking.
- Examples: "Come closer", "I want to know what you taste like"
- Audio hints: slower tempo, breathy delivery, suspended harmony
- Common in: verses, pre-choruses
- Often pairs with: `tenderness`, `tension`

## Decision flowchart

For each fragment, walk through these questions in order:

**Q1: Is there clear emotion in the lyrics/text?**

If yes → Use lyrics as the primary signal. Pick 1-2 tags that match what the
words enact (not just describe — see Principle 2 in SKILL.md).

If no → Go to Q2.

**Q2: Is there sufficient audio signal?**

If audio features are available (BPM, key, etc.) AND consistent with one
emotional reading → Pick 1 tentative tag and note it in reasoning.

If features are ambiguous OR signal is too sparse → Set `needs_user_input: true`.

**Q3: Are there mixed signals?**

If lyrics suggest one emotion but audio suggests another (e.g., dark lyrics
over a major key) → This is meaningful, not a problem. Use **both** tags
(up to 3 total). The combination itself is information.

Example output for a happy melody with sad lyrics:
```json
"emotion": ["melancholy", "playfulness"]
```

**Q4: Is your strongest tag a "core" GEMS emotion or an "extended" tag?**

Prefer extended tags when they are more precise. Example:
- "I miss you" → `loss`, not `sadness`
- "I keep thinking about that summer" → `nostalgia`, not `sadness`

Use core GEMS tags when no extended tag fits better.

## Distinctions that often confuse the model

These pairs are commonly confused. Make sure you pick the right one.

### `sadness` vs `melancholy`
- `sadness` is **present and felt**. The fragment is in the feeling.
- `melancholy` is **reflective**. The fragment is observing the feeling.

If the fragment says "I am sad" → likely `sadness`.
If the fragment says "I notice I'm always like this" → likely `melancholy`.

### `nostalgia` vs `loss`
- `nostalgia` includes sweetness. The thing recalled is precious.
- `loss` is heavier. The absence is the dominant feeling.

If "remember when" is followed by warmth → `nostalgia`.
If "remember when" is followed by ache → `loss`.

### `tension` vs `anxiety`
- `tension` can be pleasurable (anticipation, suspense in storytelling).
- `anxiety` is unpleasant (fear-driven, want-it-to-stop).

A pre-chorus building to a big chorus → `tension`.
A verse about checking your phone obsessively → `anxiety`.

### `acceptance` vs `peacefulness`
- `acceptance` is hard-won. It implies a struggle that preceded it.
- `peacefulness` is unearned calm. It can be present from the start.

"I'm finally okay with this" → `acceptance`.
"The morning is quiet" → `peacefulness`.

### `power` vs `defiance`
- `power` does not require an opponent. It's self-sufficient.
- `defiance` is power *in opposition to* something.

"I built this" → `power`.
"You said I couldn't, but I did" → `defiance`.

### `joyful_activation` vs `playfulness`
- `joyful_activation` is full-body, sustained joy.
- `playfulness` is lighter, often flirtatious or teasing.

A celebratory chorus → `joyful_activation`.
A flirty verse → `playfulness`.

## Emoji map

When a fragment is emoji-only or includes emojis, use these mappings as
starting points. Single emoji → single emotion. Multiple emojis → blend.

| Emoji | Primary emotion candidates |
|---|---|
| 🌧️ | melancholy, peacefulness, tenderness |
| 💔 | loss, sadness, melancholy |
| 🔥 | power, anger, desire, tension |
| 🌅 | peacefulness, wonder, acceptance |
| 🌙 | melancholy, longing, tenderness |
| ⭐ | wonder, joyful_activation, longing |
| 🥀 | loss, melancholy, nostalgia |
| 🎢 | joyful_activation, tension, playfulness |
| 😶‍🌫️ | vulnerability, melancholy, anxiety |
| 🦋 | tenderness, vulnerability, wonder |
| 🌊 | acceptance, peacefulness, melancholy |
| 🕯️ | tenderness, vulnerability, peacefulness |
| ⛈️ | anxiety, tension, anger |
| 🎭 | vulnerability, melancholy, defiance |
| 🪞 | vulnerability, melancholy, acceptance |
| 🏚️ | nostalgia, loss, loneliness |
| 🎈 | playfulness, joyful_activation, longing |
| 🥃 | melancholy, loneliness, acceptance |
| ❄️ | loneliness, melancholy, peacefulness |
| 🌸 | tenderness, wonder, nostalgia |

When an emoji is not in this map, attempt to map it to the closest emotion
based on common cultural associations. When unclear, set
`needs_user_input: true` rather than guess.

## What is NOT in this taxonomy

These are deliberately excluded because they are either too vague, too
clinical, or not music-relevant:

- "happy" → too generic; use `joyful_activation`, `peacefulness`, or
  `playfulness`
- "depressed" → clinical term; use `sadness`, `melancholy`, or `loneliness`
- "bitter" → not a music emotion; use `anger` or `defiance` if active,
  `melancholy` if passive
- "confused" → not really an emotion; if the fragment expresses confusion,
  it's usually `anxiety` or `vulnerability`
- "epic" → not an emotion; this is style/production talk
- "vibey" → not an emotion; this is style/production talk

If you find yourself reaching for one of these, look at the 20 tags above and
pick the closest fit. If nothing fits, set `needs_user_input: true`.

## Citations

Zentner, M., Grandjean, D., & Scherer, K. R. (2008). Emotions evoked by the
sound of music: Characterization, classification, and measurement. *Emotion*,
8(4), 494–521. https://doi.org/10.1037/1528-3542.8.4.494
