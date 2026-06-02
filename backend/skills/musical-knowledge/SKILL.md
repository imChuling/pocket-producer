---
name: musical-knowledge
description: |
  Provides objective music theory rules for evaluating compatibility between
  fragments. Used primarily by relationship-rules and Producer Agent to
  determine whether two fragments can plausibly belong to the same song
  based on key compatibility, tempo relationships, and genre conventions.
  This skill is descriptive of established music theory; it does not generate
  musical content.
license: Apache-2.0
---

# Musical Knowledge

Provide objective music theory rules for evaluating whether two fragments
are musically compatible. Purely referential — this skill answers questions,
it does not act on fragments or generate musical content.

## When to use this skill

Use this skill when:

1. The `relationship-rules` skill asks you to evaluate
   `musical_compatibility` between two fragments.
2. The Producer Agent is generating a next-step suggestion that involves
   musical specifics (e.g., "try this in Am" or "this could be a chorus
   continuation in the relative major").
3. You need to explain a musical decision to the user in plain language.

## When NOT to use this skill

- Both fragments are pure text — musical compatibility is `n/a`
- Audio features are missing or unreliable for both fragments
- The question is about emotion or theme (those have their own taxonomies
  in `music-tagging`)
- You need to generate musical content (chords, melodies, beats) — this
  skill is descriptive only

## Input

You receive two sets of audio features (one per fragment) as extracted by
librosa. Either or both may be absent.

```json
{
  "fragment_a": {
    "estimated_key": "Am",
    "estimated_mode": "minor",
    "bpm": 72.0,
    "duration_sec": 12.4,
    "pitch_range": [220.0, 440.0],
    "energy_mean": 0.042,
    "brightness": 2100.5
  },
  "fragment_b": {
    "estimated_key": "C",
    "estimated_mode": "major",
    "bpm": 68.0,
    "duration_sec": 30.1,
    "pitch_range": [196.0, 523.0],
    "energy_mean": 0.058,
    "brightness": 1800.2
  }
}
```

If a fragment has no audio features (pure text), set
`musical_compatibility: "n/a"` in the relationship output and skip this
skill entirely for that pair.

## Output schema

When consulted, return a compatibility assessment:

```json
{
  "key_compatibility": "strong | marginal | conflicting | unknown",
  "tempo_compatibility": "strong | marginal | conflicting | unknown",
  "style_compatibility": "compatible | possible | unlikely | unknown",
  "musical_compatibility": "strong | weak | conflicting | n/a",
  "reasoning": "string"
}
```

### How fields combine into `musical_compatibility`

Key and tempo are the primary signals. Style is a secondary modifier.

| key_compat | tempo_compat | → musical_compatibility |
|---|---|---|
| strong | strong | **strong** |
| strong | marginal | **weak** |
| marginal | strong | **weak** |
| marginal | marginal | **weak** |
| conflicting | any | **conflicting** |
| any | conflicting | **conflicting** |
| unknown | unknown | **n/a** |

Style compatibility **modifies** the result only at the boundaries:
- If key + tempo = `weak` AND style = `unlikely` → upgrade to
  `conflicting` (style mismatch adds weight to an already uncertain case)
- If key + tempo = `weak` AND style = `compatible` → keep `weak` (style
  alone cannot upgrade to `strong`)
- In all other cases, style does not change the combined result

A match on one primary dimension and a conflict on the other is
**conflicting overall**, not "partial match".

## Procedure

Follow these steps whenever you need to evaluate musical compatibility
between two fragments.

### Step 1: Check availability

If either fragment lacks `audio_features` entirely, return
`musical_compatibility: "n/a"` and stop.

If one fragment has audio features and the other doesn't, you can still
return `key_compatibility` or `tempo_compatibility` as `unknown` (not
`n/a` — the data is missing, not inapplicable).

### Step 2: Normalize raw values

Before comparing, apply corrections for known librosa quirks:

- **BPM normalization**: if BPM > 200, halve it; if BPM < 40, double it.
  librosa often double- or half-counts.
- **Key normalization**: if `estimated_key` is `null` or `"unknown"`, set
  `key_compatibility: "unknown"`. Do not guess.
- **Duration check**: if `duration_sec < 5`, BPM detection is unreliable.
  Set `tempo_compatibility: "unknown"` and evaluate key only.

### Step 3: Evaluate key compatibility

Compare `estimated_key` values using the rules and reference tables below.

### Step 4: Evaluate tempo compatibility

Compare `bpm` values using the thresholds and algorithm below.

### Step 5: Evaluate style compatibility (if available)

If both fragments have non-empty `style` arrays in their tags, check
the style compatibility table below. Otherwise set
`style_compatibility: "unknown"` (most fragments have empty style).

### Step 6: Combine into overall assessment

Use the combination table from the Output schema section. Write a 1-2
sentence `reasoning` that names the specific keys, BPMs, and (if
applicable) styles, and explains why they are or aren't compatible.

### Step 7: Return result

Return the JSON object. Do not suggest what the user should do — that is
the Producer Agent's job.

## Core principle: Compatibility, not correctness

A song "in Am" can move through C, F, G, and back without leaving the
listener's sense of "this is one song". Two fragments with different keys
may still belong to the same song if their keys are compatible.

Conversely, two fragments in the exact same key may not belong to the
same song if their tempos or feels are fundamentally different.

**Compatibility = "could these coexist in a single piece of music without
sounding jarring"**, not "do these have identical features".

The answers here are based on Western tonal music theory. They are
approximate and conventional, not mathematically perfect. Many great songs
break these rules. Use this skill as a default expectation, not a hard
constraint.

---

## Key Compatibility

### The four core relationships

Two keys are **strongly compatible** if they satisfy ANY of these:

1. **Same key.** Am ↔ Am. Self-evident.

2. **Relative major/minor.** Share the same key signature (same set of
   notes). Every major key has exactly one relative minor and vice versa.
   - C major ↔ A minor
   - G major ↔ E minor
   - D major ↔ B minor
   - A major ↔ F# minor
   - E major ↔ C# minor
   - F major ↔ D minor
   - Bb major ↔ G minor
   - Eb major ↔ C minor

3. **Parallel major/minor.** Same root note, different mode.
   - C major ↔ C minor
   - A major ↔ A minor
   - E major ↔ E minor
   Common for verse-chorus contrast (verse in minor, chorus lifts to
   parallel major).

4. **Circle of fifths neighbors.** One fifth apart in either direction.
   - C ↔ G, C ↔ F
   - G ↔ D, G ↔ C
   - D ↔ A, D ↔ G
   - A ↔ E, A ↔ D
   - Am ↔ Em, Am ↔ Dm
   - Em ↔ Bm, Em ↔ Am

Two keys are **marginally compatible** if:
- They are a whole step apart (C ↔ D, Am ↔ Bm)
- They are a minor third apart (C ↔ Eb, C ↔ A)
- They share ≥ 4 common scale tones but don't meet any strong criterion

Two keys are **conflicting** if:
- They are a tritone apart (C ↔ F#, G ↔ C#, E ↔ Bb)
- They share ≤ 3 common scale tones
- No strong or marginal relationship applies

### Complete key reference table: Major keys

| Key | Relative minor | Fifth up | Fifth down | Parallel minor |
|---|---|---|---|---|
| C | Am | G | F | Cm |
| G | Em | D | C | Gm |
| D | Bm | A | G | Dm |
| A | F#m | E | D | Am |
| E | C#m | B | A | Em |
| B | G#m | F# | E | Bm |
| F# | D#m | C# | B | F#m |
| F | Dm | C | Bb | Fm |
| Bb | Gm | F | Eb | Bbm |
| Eb | Cm | Bb | Ab | Ebm |
| Ab | Fm | Eb | Db | Abm |
| Db | Bbm | Ab | Gb | C#m |

### Complete key reference table: Minor keys

| Key | Relative major | Fifth up | Fifth down | Parallel major |
|---|---|---|---|---|
| Am | C | Em | Dm | A |
| Em | G | Bm | Am | E |
| Bm | D | F#m | Em | B |
| F#m | A | C#m | Bm | F# |
| C#m | E | G#m | F#m | C# |
| G#m | B | D#m | C#m | G# |
| Dm | F | Am | Gm | D |
| Gm | Bb | Dm | Cm | G |
| Cm | Eb | Gm | Fm | C |
| Fm | Ab | Cm | Bbm | F |
| Bbm | Db | Fm | Ebm | Bb |
| Ebm | Gb | Bbm | Abm | Eb |

### Key compatibility algorithm

```
def key_compatible(K1, K2):
    if K1 == K2:
        return "strong"           # same key

    if are_relative(K1, K2):
        return "strong"           # relative major/minor

    if are_parallel(K1, K2):
        return "strong"           # parallel major/minor

    if are_fifth_apart(K1, K2):
        return "strong"           # circle of fifths neighbors

    if are_whole_step_apart(K1, K2):
        return "marginal"

    if are_minor_third_apart(K1, K2):
        return "marginal"

    return "conflicting"
```

### librosa key detection: known failure modes

librosa's `librosa.feature.chroma_cqt` + `Krumhansl-Schmuckler` key
detection has these known issues:

- **Relative major/minor confusion**: Am is often detected as C (and vice
  versa) because they share the same note set. **Rule**: always treat
  relative major/minor pairs as `strong` — they may be the same tonal
  center detected differently.
- **Weak chroma signal**: short, noisy, or percussive audio produces
  unreliable key. If `duration_sec < 5` or the audio is percussive with
  no pitched content, set `key_compatibility: "unknown"`.
- **Enharmonic spelling**: librosa may report Db where you expect C#.
  Treat as identical (Db = C#, Gb = F#, etc.).

### Modal scales

When a fragment is described as modal (Dorian, Mixolydian, etc.), map to
the parent major key for compatibility purposes:

| Mode | Example | Parent major key |
|---|---|---|
| Dorian | D Dorian | C major |
| Phrygian | E Phrygian | C major |
| Lydian | F Lydian | C major |
| Mixolydian | G Mixolydian | C major |
| Aeolian (natural minor) | A Aeolian | C major |

General rule: the mode's parent is the major key whose scale contains
the same notes. For any mode on note X, find which major scale includes
X as a scale degree.

If the user has explicitly stated a mode ("I wrote this in F# Dorian"),
trust the user over librosa. F# Dorian → parent key E major → evaluate
compatibility against E major.

---

## Tempo Compatibility

### The four compatibility zones

**Zone 1: Strong (within 10%)**

Two fragments within 10% of each other's BPM feel like the same tempo.

| BPM A | Strong range (±10%) |
|---|---|
| 60 | 54 – 66 |
| 72 | 65 – 79 |
| 80 | 72 – 88 |
| 90 | 81 – 99 |
| 100 | 90 – 110 |
| 120 | 108 – 132 |
| 140 | 126 – 154 |
| 160 | 144 – 176 |

**Zone 2: Doubled/halved (strong)**

A fragment at 72 BPM and another at 144 BPM can be the same musical idea
at "double time" feel. The doubled/halved range tolerates ±10%:

- 72 ↔ 144 → strong (exactly 2×)
- 72 ↔ 140 → strong (2× within 5%)
- 72 ↔ 150 → strong (2× within 5%)
- 72 ↔ 160 → marginal (2× but 11% off — borderline)

This matters because songwriters frequently sketch at half-time and
perform at full tempo (especially common in trap: felt 70 BPM, detected
140 BPM).

**Zone 3: Marginal (10-25%, or 1.5× relationship)**

Two fragments within 10-25% of each other might be the same song with
one section slowed or rushed. A 1.5× relationship (e.g., 80 ↔ 120) is
possible but unusual — sometimes indicates triplet feel vs straight feel.

**Zone 4: Conflicting (>25% and not 2× related)**

Different songs. Examples:
- 70 BPM ballad vs 110 BPM mid-tempo (57% apart, not 2×)
- 90 BPM verse vs 150 BPM chorus (67% apart, not 2×)

### Tempo compatibility algorithm

```
def tempo_compatible(BPM_A, BPM_B):
    # normalize extremes first
    if BPM_A > 200: BPM_A /= 2
    if BPM_A < 40:  BPM_A *= 2
    if BPM_B > 200: BPM_B /= 2
    if BPM_B < 40:  BPM_B *= 2

    ratio = max(BPM_A, BPM_B) / min(BPM_A, BPM_B)

    # within 10% → strong
    if ratio <= 1.10:
        return "strong"

    # doubled/halved (2× ± 10%) → strong
    if 1.90 <= ratio <= 2.10:
        return "strong"

    # within 25% → marginal
    if ratio <= 1.25:
        return "marginal"

    # 1.5× relationship (± 10%) → marginal
    if 1.40 <= ratio <= 1.60:
        return "marginal"

    return "conflicting"
```

### BPM = 0 or no rhythmic content

librosa returns 0 BPM for ambient, drone, or free-time audio. In this
case:
- Set `tempo_compatibility: "unknown"`
- Evaluate compatibility based on key alone
- If neither tempo nor key is detectable, return
  `musical_compatibility: "n/a"`

### Common songwriter tempo categories

Useful context for Producer Agent when explaining decisions:

| Category | BPM range | Typical styles |
|---|---|---|
| Bedroom ballad | 60–80 | indie-folk, acoustic-ballad, singer-songwriter, blues (slow), soul (ballad) |
| Walking mid-tempo | 90–110 | pop, alt-pop, r&b, neo-soul, soft-rock, dream-pop |
| Dance / four-on-floor | 120–128 | pop, synth-pop, electronic |
| Driving / upbeat | 130–150 | indie-rock, rock, post-punk, psychedelic-rock |
| Fast / aggressive | 160–220 | punk, metal (thrash), metalcore |
| Trap (half-time felt) | detected 70–90, felt 140–180 | trap, hip-hop |
| Variable / unreliable | depends on section | math-rock, progressive-rock, post-rock, jazz, fusion |

Two fragments in **different categories** (e.g., bedroom ballad vs
driving rock) that are NOT in a doubled/halved relationship are almost
certainly different songs, even if detected BPMs happen to be within 25%.

---

## Style Compatibility

Style is the **weakest** of the three signals because most fragments have
empty style arrays. When both fragments have non-empty style tags, use the
tables below. When either is empty, set `style_compatibility: "unknown"`
and rely on key + tempo only.

### Compatible style pairs

These styles can naturally appear in the same song:

| Style A | Style B |
|---|---|
| indie-folk | singer-songwriter |
| indie-folk | acoustic-ballad |
| acoustic-ballad | singer-songwriter |
| pop | alt-pop |
| pop | synth-pop |
| bedroom-pop | alt-pop |
| bedroom-pop | lo-fi |
| hip-hop | r&b |
| hip-hop | trap |
| indie-rock | rock |
| indie-rock | alt-pop |
| dream-pop | shoegaze |
| soul | r&b |
| neo-soul | r&b |
| neo-soul | soul |
| neo-soul | jazz |
| blues | rock |
| blues | soul |
| metal | metalcore |
| punk | metalcore |
| punk | post-punk |
| post-rock | ambient |
| shoegaze | indie-rock |
| psychedelic-rock | rock |
| progressive-rock | rock |
| soft-rock | rock |
| soft-rock | pop |
| art-pop | alt-pop |
| art-pop | synth-pop |
| dream-pop | ambient |

Set `style_compatibility: "compatible"`.

### Possible but unusual pairs

These require deliberate artistic intention:

| Style A | Style B | Why possible |
|---|---|---|
| acoustic-ballad | electronic | e.g., Bon Iver later work |
| r&b | electronic | modern alt-R&B crossover |
| indie-folk | lo-fi | lo-fi folk aesthetic |
| hip-hop | synth-pop | cross-genre production |
| jazz | hip-hop | jazz rap (A Tribe Called Quest) |
| jazz | electronic | nu-jazz / jazztronica |
| blues | jazz | blues-jazz crossover |
| fusion | progressive-rock | prog-fusion |
| metal | progressive-rock | progressive metal (Tool) |
| psychedelic-rock | shoegaze | psych-shoegaze |
| post-punk | shoegaze | darkgaze |
| post-punk | synth-pop | dark synth-pop crossover |
| art-pop | electronic | art-electronic (FKA twigs) |
| dream-pop | indie-folk | atmospheric folk |
| neo-soul | lo-fi | lo-fi neo-soul production |
| metalcore | electronic | modern hybrid metalcore |
| post-rock | progressive-rock | expansive, atmospheric |

Set `style_compatibility: "possible"`.

### Rarely compatible pairs

These usually indicate different songs:

- trap + indie-folk
- punk + r&b
- ambient + pop
- experimental + most others
- metal + acoustic-ballad
- metal + indie-folk
- metalcore + dream-pop
- trap + jazz
- blues + trap
- blues + electronic
- punk + dream-pop
- math-rock + hip-hop
- jazz + punk
- soul + metal

Set `style_compatibility: "unlikely"`.

### Typical genre conventions (quick reference)

For each style tag, the key structural expectations. Full details in
`references/genre-conventions.md`.

| Style | Typical BPM | Typical keys | Structure |
|---|---|---|---|
| indie-folk | 60–100 | minor / modal | verse-chorus, high lyric density |
| singer-songwriter | 60–110 | any | classic verse-chorus, intimate |
| acoustic-ballad | 60–80 | any | simple verse-chorus, minimal |
| pop | 100–130 | major dominant | V-PC-C-V-PC-C-Br-C, ~3.5 min |
| alt-pop | 90–130 | minor / modal | pop forms with irregularities |
| bedroom-pop | 80–130 | any | looser forms, lo-fi aesthetic |
| synth-pop | 100–130 | minor w/ major chorus | synth-led, programmed drums |
| art-pop | 80–130 | any, tonal ambiguity | unconventional, concept-driven |
| dream-pop | 80–120 | any | blurred sections, reverb-drenched |
| hip-hop | 70–100 (felt 140–180) | minor / modal | verse-hook-verse-hook |
| trap | 70–90 (felt 140–180) | dark minor | verse-hook, 808s, triplet hi-hats |
| r&b | 70–100 | minor, complex chords | verse-prechorus-chorus |
| soul | 60–120 | major / minor, gospel | verse-chorus, call-and-response |
| neo-soul | 70–110 | minor, jazz harmony | verse-chorus, vamp outros |
| jazz | 50–200+ | all, extended harmony | head-solos-head, AABA / 12-bar |
| blues | 60–130 | open guitar keys, blue notes | 12-bar blues, AAB lyric form |
| fusion | 80–160 | complex, odd meters | long-form, head-solo-head |
| electronic | 100–140 | any | build-drop, synth central |
| ambient | no BPM | modal / atonal | through-composed, drones |
| lo-fi | 70–100 | jazz-influenced | looped / short forms |
| rock | 100–150 | any | classic verse-chorus-bridge |
| indie-rock | 100–150 | any | verse-chorus-bridge, guitars |
| soft-rock | 80–120 | major dominant | verse-chorus-bridge, vocal harmony |
| post-rock | 60–140 (shifts) | modal / ambiguous | crescendo arcs, 5–15 min |
| math-rock | 100–160 (unreliable) | modal / ambiguous | through-composed, meter shifts |
| shoegaze | 80–130 | any (obscured) | blurred verse-chorus, textural |
| psychedelic-rock | 80–140 | modal (Mixolydian) | extended, improvisatory |
| progressive-rock | 60–180 (shifts) | complex, modulating | multi-section suites, 5–20 min |
| punk | 140–200 | simple major/minor | short, direct, 2–3 min |
| post-punk | 100–150 | minor, bass-led melody | angular, driving, dark |
| metal | 60–220 (by subgenre) | minor, drop tunings | riff-driven, often 4–8 min |
| metalcore | 100–180 (shifts) | minor, drop tunings | verse-chorus + breakdowns |
| experimental | any | any / atonal | non-narrative, sound design |
| world-fusion | varies | varies | needs user description |

---

## Edge cases

### librosa key detection disagreement (relative major/minor)

librosa sometimes reports the relative major instead of the minor (e.g.,
C instead of Am). If two fragments report keys that are relative
major/minor of each other, treat them as `strong` — they are likely the
same tonal center detected differently. This is the most common librosa
"error" and should always be handled gracefully.

### Very short fragments (< 5 seconds)

librosa's BPM detection is unreliable for very short audio. If
`duration_sec < 5`, set `tempo_compatibility: "unknown"` and rely only
on key compatibility.

### No key detected

If librosa returns `null` or `"unknown"` for `estimated_key`, set
`key_compatibility: "unknown"`. Do not guess.

### Extreme BPM values

BPM above 200 or below 40 usually indicates librosa double/half-counting.
Normalize: if BPM > 200, halve it; if BPM < 40, double it. Then compare.

### Enharmonic equivalents

Db = C#, Gb = F#, Ab = G#, etc. librosa may report either spelling.
Treat them as identical.

### Both fragments have BPM but no key (percussive audio)

Drum loops, beatboxing, and rhythmic sketches may have reliable BPM but
no meaningful key. Evaluate tempo only; set
`key_compatibility: "unknown"`.

### Trap half-time detection

Trap music is commonly detected at 70-90 BPM by librosa but is felt at
140-180 BPM. If one fragment has a `trap` or `hip-hop` style tag and its
BPM is 65-95, also check its double (130-190) against the other fragment.
This prevents false `conflicting` between a trap verse and a pop chorus
that are actually tempo-compatible.

---

## Worked examples

### Example 1: Strong compatibility (relative keys, close BPM)

Fragment A: Am, 72 BPM
Fragment B: C major, 68 BPM

- Key: Am ↔ C = relative major/minor → `strong`
- Tempo: |72 - 68| / 72 = 5.6% → `strong` (within 10%)
- Style: both empty → `unknown`
- Overall: `strong`
- Reasoning: "Am and C major are relative keys (strongly compatible), and
  68 vs 72 BPM is a negligible tempo difference."

### Example 2: Half-time relationship

Fragment A: Em, 140 BPM, style: [indie-rock]
Fragment B: Em, 70 BPM, style: [singer-songwriter]

- Key: Em ↔ Em = identical → `strong`
- Tempo: 140 / 70 = 2.0× → `strong` (doubled/halved)
- Style: indie-rock + singer-songwriter → not in compatible pairs, but
  not in "unlikely" either → `possible`
- Overall: `strong` (style doesn't downgrade strong key+tempo)
- Reasoning: "Same key; 140 BPM is exactly double 70 BPM, suggesting a
  half-time/double-time relationship within the same musical idea."

### Example 3: Key conflict blocks compatibility

Fragment A: F# major, 120 BPM
Fragment B: C major, 118 BPM

- Key: F# ↔ C = tritone apart → `conflicting`
- Tempo: |120 - 118| / 120 = 1.7% → `strong`
- Overall: `conflicting` (key conflict overrides tempo match)
- Reasoning: "F# and C major are a tritone apart with no natural
  modulation pathway. Despite nearly identical tempos, these fragments
  are musically incompatible."

### Example 4: Marginal — key strong, tempo borderline

Fragment A: D major, 90 BPM
Fragment B: A major, 112 BPM

- Key: D ↔ A = one fifth apart → `strong`
- Tempo: |112 - 90| / 90 = 24.4% → `marginal` (within 25%)
- Overall: `weak`
- Reasoning: "D and A major are circle-of-fifths neighbors (compatible),
  but 90 vs 112 BPM is a significant tempo difference that would require
  intentional contrast if used in the same song."

### Example 5: Missing data (one fragment is text-only)

Fragment A: Dm, 85 BPM
Fragment B: (pure text, no audio features)

- Key: unknown (no data for B)
- Tempo: unknown
- Overall: `n/a`
- Reasoning: "Fragment B has no audio features; musical compatibility
  cannot be evaluated."

### Example 6: Extreme BPM normalization

Fragment A: Gm, 156 BPM, style: [trap]
Fragment B: Gm, 78 BPM, style: [hip-hop]

- Key: Gm ↔ Gm = identical → `strong`
- Tempo: 156 / 78 = 2.0× → `strong` (doubled/halved — classic trap
  half-time feel)
- Style: trap + hip-hop → `compatible`
- Overall: `strong`
- Reasoning: "Same key; 156 BPM is double 78 BPM, consistent with trap
  half-time feel. Style tags confirm the same genre family."

### Example 7: Style mismatch adds weight to weak signal

Fragment A: Cm, 95 BPM, style: [trap]
Fragment B: Eb major, 110 BPM, style: [indie-folk]

- Key: Cm ↔ Eb = relative major/minor → `strong`
- Tempo: |110 - 95| / 95 = 15.8% → `marginal`
- Style: trap + indie-folk → `unlikely`
- Key + tempo alone → `weak` (strong key + marginal tempo)
- Style modifier: `unlikely` upgrades `weak` → `conflicting`
- Overall: `conflicting`
- Reasoning: "Cm and Eb major are relative keys, but the 16% tempo
  difference combined with a trap/indie-folk style mismatch suggests
  these are different songs despite the key relationship."

### Example 8: Modal scale handling

Fragment A: user described as "D Dorian", 100 BPM
Fragment B: C major, 96 BPM

- D Dorian maps to parent key C major
- Key: C major ↔ C major = identical → `strong`
- Tempo: |100 - 96| / 100 = 4% → `strong` (within 5%)
- Overall: `strong`
- Reasoning: "D Dorian shares its note set with C major (parent key).
  BPMs are nearly identical. Strongly compatible."

### Example 9: Percussive audio — tempo only

Fragment A: no key (beatbox), 92 BPM
Fragment B: Am, 88 BPM

- Key: unknown (A has no pitched content) → `unknown`
- Tempo: |92 - 88| / 92 = 4.3% → `strong` (within 5%)
- Overall: key unknown + tempo strong → cannot be `strong` overall.
  Return `weak` with reasoning noting the limitation.
- Reasoning: "Tempos are very close (92 vs 88 BPM), but the beatbox
  fragment has no key information. Tempo suggests compatibility; key
  cannot be confirmed."

### Example 10: librosa relative-key confusion

Fragment A: librosa reports "C major", 75 BPM
Fragment B: librosa reports "Am", 72 BPM
User context: both fragments are described as "minor-key piano"

- Key: C ↔ Am = relative major/minor → `strong`
  (and likely the same tonal center — librosa probably detected C for a
  fragment that is actually in Am)
- Tempo: |75 - 72| / 75 = 4% → `strong`
- Overall: `strong`
- Reasoning: "C major and Am are relative keys and likely the same tonal
  center (librosa commonly confuses them). Tempos are nearly identical."

---

## Common mistakes

1. **Treating key match as sufficient evidence for same-song.** Two
   fragments in Am at different tempos and with different emotions are
   probably NOT the same song. Key compatibility is one signal out of
   four in `relationship-rules`. Always defer to the full multi-signal
   evaluation.

2. **Ignoring half-time/double-time.** 72 BPM and 144 BPM are musically
   the same idea. Many producers sketch at half-time and perform at full
   tempo. Always check for the 2× relationship before marking
   `conflicting`.

3. **Over-relying on librosa output.** librosa's key detection has known
   failure modes (relative major/minor confusion, weak chroma signals,
   enharmonic spelling). When the detected key seems implausible given
   other context, return `unknown` rather than `conflicting`.

4. **Forgetting BPM normalization.** A fragment at 210 BPM is almost
   certainly detected at 2× the real tempo. Normalize before comparing.

5. **Going too deep into theory.** If you find yourself reasoning about
   modal interchange, Neapolitan chords, or chromatic mediants — stop.
   Return `marginal` and let the user judge. This skill provides defaults,
   not advanced harmonic analysis.

6. **Ignoring trap half-time.** Trap fragments detected at 70-90 BPM are
   felt at double that. Always check both the raw BPM and its double when
   a trap or hip-hop style tag is present.

7. **Using style as a primary signal.** Style is the weakest signal —
   most fragments have empty style arrays, and genre boundaries are
   fluid. Style should only modify an already-formed key+tempo judgment,
   never drive it.

8. **Generating musical suggestions.** This skill does not tell the user
   "try playing in G major" or "add a chord progression". That is the
   Producer Agent's job. Return the assessment and stop.

## What this skill does NOT do

- Generate musical content (chord progressions, melodies, riffs, beats)
- Judge musical quality or originality
- Act on fragments (no writes, no project changes)
- Evaluate non-musical compatibility (emotion, theme — separate skills)
- Override the user's stated musical intent
- Provide advanced harmonic analysis (beyond the rules defined here)

Stay within compatibility assessment. For the full reference tables with
additional context, see:
- `references/key-compatibility.md` — complete theory and pseudocode
- `references/tempo-rules.md` — zone details and special cases
- `references/genre-conventions.md` — style-by-style structural norms

Other agents and skills handle the rest.
