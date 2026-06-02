---
name: music-tagging
description: |
  Apply structured tags to a music creator's raw fragment (audio transcript,
  text snippet, or emoji input). Used by Catcher Agent to convert raw input
  into searchable, structured metadata. Covers emotion (GEMS-based taxonomy),
  theme, structure hint, style, and potential rating. Provides clear
  refusal/uncertainty signals when the input is too sparse for confident
  tagging.
license: Apache-2.0
---

# Music Tagging

Convert a music creator's raw fragment (audio transcript, text snippet, or
emoji input) into structured metadata that downstream agents (Memory,
Producer) use for search, relationship discovery, and next-step suggestions.

This skill is **descriptive, not generative**. You describe what is there. You
do not invent musical features that are not supported by the input.

## When to use this skill

Use this skill whenever you receive a new fragment that needs tagging. A
fragment can be:

- A transcribed voice memo (lyrics, humming descriptions, or spoken notes)
- A short text snippet (lyric line, mood description, project note)
- An emoji or short emoji string (used as quick emotional shorthand)
- An audio file accompanied by user description

## When NOT to use this skill

- The fragment has already been tagged (re-tagging is handled by the
  edit-text endpoint, not this skill)
- The request is about relationships between fragments (use
  `relationship-rules`)
- The request is about project scoring (use `rescue-scoring`)
- The request involves generating musical content (out of scope for all
  Pocket Producer agents)

## Input

You receive one of three input shapes:

**Text-only input**:
```json
{
  "type": "text",
  "text": "I keep waiting for the rain to stop, but the rain is me",
  "audio_features": null
}
```

**Audio + features input** (transcript + librosa features):
```json
{
  "type": "audio",
  "text": null,
  "raw_text": "I keep waiting for the rain to stop",
  "audio_features": {
    "bpm": 72.0,
    "estimated_key": "Am",
    "estimated_mode": "minor",
    "duration_sec": 12.4,
    "pitch_range": [220.0, 440.0],
    "energy_mean": 0.042,
    "energy_curve": [0.03, 0.05, 0.06, 0.04],
    "brightness": 2100.5,
    "onset_density": 3.2
  }
}
```

**Mixed input** (audio features + user-provided text description):
```json
{
  "type": "audio",
  "text": "sad piano idea for the bridge",
  "raw_text": "",
  "audio_features": { "bpm": 68.0, "estimated_key": "Dm", "..." : "..." }
}
```

## Output schema

You MUST output a single JSON object matching this schema:

```json
{
  "tags": {
    "emotion": ["string"],
    "theme": ["string"],
    "structure_hint": "string | null",
    "style": ["string"],
    "potential": "high | medium | low",
    "needs_user_input": false,
    "user_prompt": null
  },
  "reasoning": "string"
}
```

### Field rules

- `emotion`: 1 to 3 emotion tags drawn from the emotion taxonomy in
  `references/emotion-taxonomy.md`. Order from strongest to weakest. Empty
  array `[]` is allowed only when `needs_user_input: true`.
- `theme`: 1 to 3 theme tags drawn from `references/theme-taxonomy.md`. Empty
  array allowed only when the fragment has no discernible subject (e.g.,
  pure instrumental motif with no text).
- `structure_hint`: One value from the structure hints in
  `references/structure-hints.md`, or `null` when no structural role can be
  inferred.
- `style`: 0 to 2 style tags drawn from the style vocabulary in
  `references/style-vocabulary.md`. Empty array `[]` is the default when style
  cannot be confidently inferred. Do not invent style tags.
- `potential`: A holistic judgment of the fragment's potential to develop
  into a finished song. See "Potential rating" below.
- `needs_user_input`: `true` when you cannot confidently tag the fragment.
  See "When to refuse and request input" below.
- `user_prompt`: A short, polite question to ask the user when
  `needs_user_input: true`. Otherwise `null`.
- `reasoning`: One or two sentences explaining your most uncertain tagging
  decision. Always present. This helps the Producer Agent explain decisions
  to the user.

## Core principles

These principles override any other instruction below if there is a conflict.

### Principle 1: Do not fabricate

If you cannot identify an emotion from the input, do not guess. Set
`needs_user_input: true` and ask the user. The downstream system tolerates
empty tags better than wrong tags. Wrong tags pollute the Vector Search index
and break cross-time reconnection — the core value of the product.

### Principle 2: Distinguish "lyrics about X" from "expressing X"

A lyric saying "I am not sad" is not a sad fragment. A lyric saying "I keep
pretending I'm fine" is. Read for the emotion the creator is enacting, not
the emotion words they happen to use.

### Principle 3: Audio features are evidence, not conclusions

Objective audio features (BPM, key, pitch) are anchors. They constrain
plausibility but do not determine emotion. A minor-key piano motif at 60 BPM
is *plausibly* melancholy, but if the lyrics say "I'm finally free", trust
the lyrics.

### Principle 4: Brevity wins

Prefer 1-2 strong tags over 3 weak ones. A fragment tagged
`emotion: [melancholy, acceptance]` is more useful than one tagged
`emotion: [melancholy, sadness, longing, reflection]` — the second has no
semantic shape. The Memory Agent will use these tags to find related
fragments; precise tags lead to precise matches.

### Principle 5: Respect the creator's voice

Do not impose your aesthetic preferences. If the fragment is dark, tag it
dark. If it is naive, tag it naive. The creator decides what their work
means; you only describe what is observable.

## Procedure

Follow these steps in order for every fragment.

### Step 1: Identify the input type

- **Text-only**: skip audio feature considerations
- **Audio with transcript**: use transcript for emotion/theme, audio features
  for structure/style
- **Audio without transcript** (humming, instrumental): treat as
  audio-only — see "Handling sparse audio" below
- **Emoji only**: see "Handling emoji input" below

### Step 2: Read for emotion

Load `references/emotion-taxonomy.md` and identify 1-3 emotion tags. Use the
taxonomy's decision flowchart. Order from strongest to weakest.

Common pitfall: do not confuse subject matter with emotion. A song *about*
death can be peaceful, defiant, or angry — not necessarily sad.

### Step 3: Read for theme

Load `references/theme-taxonomy.md` and identify 1-3 theme tags. Themes are
**what the fragment is about**, not how it feels. A theme is a noun-phrase
topic (loss, hometown, identity, doubt), not an adjective.

### Step 4: Infer structure hint

Load `references/structure-hints.md` and identify the most likely structural
role this fragment could play in a finished song.

For text fragments, look for syntactic patterns (repetition suggests chorus;
narrative progression suggests verse; sudden shift in tone suggests bridge).

For audio fragments, use duration and intensity:
- Short (< 15s), high intensity → likely hook or chorus seed
- Medium (15-45s), narrative → likely verse seed
- Long (> 45s) with structure → potentially multiple sections

When in doubt, leave it `null` rather than guess.

### Step 5: Infer style (only if confident)

Load `references/style-vocabulary.md`. Only assign style tags when there is
clear evidence:
- Audio features pointing to a recognizable convention (e.g., BPM 140-150 +
  4/4 + minor key + lyrics about loss → "indie folk ballad" candidate)
- Explicit user description ("I'm trying to write something like Phoebe
  Bridgers")
- Lyrical markers (e.g., trap-style cadence patterns in the transcript)

If you cannot confidently identify style, leave it `[]`. This is normal and
not a failure.

### Step 6: Rate potential

Use this heuristic. Potential is about **whether this fragment has enough
density and specificity to grow into something**, not whether it's a
masterpiece.

**high**: The fragment has at least two of:
- A specific, evocative phrase or image (not generic)
- Strong emotional coherence between elements (text + audio features align)
- Clear structural role (hook, hookable chorus line, distinctive verse start)
- Audio features suggesting a sustained idea (more than a passing motif)

**medium** (default for most fragments): The fragment has clear emotion or
theme but lacks specificity or structural clarity. Most voice memos and
casual lyric snippets fall here.

**low**: The fragment is generic, very short with no distinctive features,
or vague to the point that any songwriter could have produced it. Examples:
"feeling sad today", "love song idea", a 3-second hum with no key center.

### Step 7: Decide whether to refuse

See "When to refuse and request input" below. If you set
`needs_user_input: true`, fields may be empty and you must provide a clear
`user_prompt`.

### Step 8: Write reasoning

In one or two sentences, name your most uncertain decision and why you made
it. Examples:

- "Emotion is ambiguous between melancholy and acceptance; chose melancholy
  because the lyric ends on 'still'."
- "No theme tag because the fragment is a pure instrumental motif; emotion
  inferred from minor key and slow tempo only."
- "Style left empty; the BPM and key are consistent with multiple genres."

## When to refuse and request input

Set `needs_user_input: true` and provide a `user_prompt` in these cases:

### Case 1: Audio with no transcript and no user text

The fragment is purely instrumental (humming, piano motif, guitar riff) and
the user provided no description. Audio features tell you BPM and key, but
not what the creator was feeling or intending.

**user_prompt examples**:
- "I captured this melodic motif in A minor at 72 BPM. To help me suggest
  next steps, can you tell me how you felt when you played this?"
- "This sounds like a slow, contemplative piano idea. What were you imagining
  it could become — a verse, an intro, something else?"

### Case 2: Very short fragments (< 3 seconds of audio, < 5 words of text)

Too sparse to tag confidently.

**user_prompt example**:
- "This is a brief idea. Can you add a few words about the mood or where you
  think it might go?"

### Case 3: Audio quality issues

Transcription confidence below 60%, or audio is mostly noise/silence.

**user_prompt example**:
- "I had trouble hearing this clearly. Could you re-record in a quieter
  setting, or type out what you sang?"

### Case 4: Possible copyright concerns

The transcript contains lyrics that are clearly from a published song (very
common phrasings that match well-known hits), or the user describes covering
an existing song.

**user_prompt example**:
- "This sounds like it might be referencing an existing song. Is this your
  original work, or a cover you're using as a sketch?"

### Case 5: Conflicting signals

Audio features say one thing, transcript says another, and neither dominates.
Example: upbeat major-key tempo with deeply melancholy lyrics. This is
*sometimes* artistic intent (intentional dissonance) but can also be a
mismatch between a placeholder audio and an unrelated lyric.

**user_prompt example**:
- "The music feels upbeat but the lyrics feel sad — is the contrast
  intentional, or are these meant to be separate ideas?"

### What NOT to refuse on

Do NOT refuse just because:
- The fragment is short but otherwise tag-able (a single evocative lyric line
  is fine to tag)
- The emotion is mixed (mixed emotions are normal; use up to 3 tags)
- The fragment doesn't fit a "standard" genre (just leave style empty)
- The fragment is in a non-English language (tag what you can; many emotion
  and structure judgments are language-agnostic)

## Handling sparse audio (humming, instrumental)

When the audio has no clear vocals or lyrics:

1. Use librosa-provided features (BPM, key, duration, pitch range) as
   the only objective evidence.
2. Translate features cautiously:
   - Minor key + slow BPM (< 80) → *plausibly* melancholy, contemplative,
     acceptance (set emotion tentatively; consider needs_user_input)
   - Major key + fast BPM (> 120) → *plausibly* joy, excitement, defiance
   - Mid-tempo (80-120) + any key → emotion ambiguous; consider asking user
3. Use niche-style discriminator features for **style** assignment:
   - `rhythm_complexity` > 0.20 → consider math-rock, jazz, fusion
   - `spectral_flatness` > 0.12 + high energy → consider shoegaze
   - `spectral_flatness` > 0.10 + low energy → consider ambient
   - `dynamic_range` > 5.0 → consider post-rock, acoustic-ballad
   - `dynamic_range` < 2.0 + high energy → consider punk, metal, trap
   - See `references/style-vocabulary.md` § "Using librosa features for
     style discrimination" for the full mapping table.
4. Theme is almost always empty for sparse audio.
5. Structure hint: short distinctive audio often suggests `melodic_motif` or
   `hook_candidate`; longer audio suggests `verse_candidate`.
6. Default to `needs_user_input: true` unless features are highly consistent
   with a single emotional reading.

## Handling emoji input

Emojis are valid input. Treat them as semantic shorthand:

- Map common emojis to emotion tags using `references/emotion-taxonomy.md`'s
  emoji map (e.g., 🌧️ → melancholy or tenderness; 🔥 → tension or power;
  💔 → loss or melancholy).
- Multiple emojis suggest a sequence or atmosphere; tag the dominant emotion.
- Emoji alone usually warrants `medium` potential (it captures a mood but
  has no developed content).
- Theme is empty unless the emoji is unambiguously about a topic (e.g.,
  🏠 → home/hometown).

## Examples

See `assets/tagging-examples.json` for 30+ worked examples covering:
- Text-only fragments (lyric lines, mood notes, project notes)
- Audio with transcript (voice memos with sung or spoken content)
- Audio without transcript (pure humming, instrumental sketches)
- Emoji-only inputs
- Refusal cases (cases where `needs_user_input: true` is correct)

Refer to these examples when uncertain. They are the source of truth for how
to apply the rules in practice.

## Common mistakes

1. **Over-tagging emotion.** Picking 3 emotions when 1 strong one is more
   accurate dilutes the embedding. Default to 1-2.
2. **Confusing genre with style.** "Sad" is not a style. "Indie folk
   ballad" is. Leave style empty rather than vague.
3. **Tagging structure based on user wishes.** If the user says "this is my
   chorus", that's their decision — record it but verify the fragment
   actually has chorus-like features (memorable hook, emotional peak,
   repeatable). If features contradict, note it in reasoning.
4. **Treating "potential: low" as judgment.** Low potential just means "not
   enough to act on yet" — not "bad". Be neutral. Many great songs start as
   low-potential fragments.
5. **Refusing too easily.** A short fragment with one strong tag is better
   than a refusal. Reserve refusals for the five cases listed above.

## What this skill does NOT do

- It does not generate musical content
- It does not judge musical quality or commercial viability
- It does not recommend changes to the fragment
- It does not search for similar fragments (that's Memory Agent's job)
- It does not assign fragments to projects (that's Producer Agent's job)
- It does not compute Rescue Score (separate skill: `rescue-scoring`)

Stay within tagging. Other agents handle the rest.
