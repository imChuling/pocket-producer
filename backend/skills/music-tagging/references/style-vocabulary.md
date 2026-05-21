# Style Vocabulary

Style tags describe **the genre or sonic convention** of a fragment, when
that is clearly identifiable. Style is the most uncertain field in our
schema — assign tags only when there is real evidence.

The default is `style: []` (empty array). This is not a failure. Many
fragments have no clear genre signature, especially early sketches, hums,
and lyric snippets. An empty style is more honest than a forced guess.

## When to assign a style tag

Assign style tags only when at least one of these conditions is met:

1. **Explicit user description**: The user has said "I want this to sound
   like X" or "I'm trying for a Y feel". Use their language.

2. **Strong audio signature**: The recording has unmistakable genre markers:
   - Trap-style hi-hats and 808s → trap-leaning
   - Fingerpicked acoustic guitar at moderate tempo → folk-leaning
   - Heavily processed atmospheric pads + sparse drums → ambient/atmospheric
   - Distorted guitars + driving rock drums → rock/punk-leaning

3. **Lyric form signals**: The lyrics use a recognizable form:
   - Trap cadence (triplet flows, ad-libs)
   - Ballad structure (long descriptive verses)
   - Hip-hop verse density

4. **Clear BPM + key + tempo combination**: e.g., 140-150 BPM in minor with
   descriptive verses → indie folk or alt-pop ballad territory

When none of these apply → `style: []`.

## The 18 style tags

These are intentionally broad genre families, not specific micro-genres. The
goal is to enable useful semantic retrieval, not to be a music encyclopedia.

### Singer-songwriter cluster

#### `indie-folk`
Acoustic-based, lyric-forward, often introspective. Moderate tempo. Vocal
prominent over sparse instrumentation.
- Audio markers: acoustic guitar or piano lead, moderate dynamics
- Reference points: Phoebe Bridgers, Bon Iver, Sufjan Stevens

#### `singer-songwriter`
Generic singer-songwriter feel — acoustic or piano-led, narrative lyrics,
moderate everything. Use when more specific tags don't fit.
- Audio markers: one main instrument + voice, conversational delivery

#### `acoustic-ballad`
Slow, intimate, often emotional peak in a quiet way. Voice and one
instrument is the typical texture.
- Audio markers: BPM < 80, sparse arrangement, dynamic restraint

### Pop cluster

#### `pop`
Bright, catchy, accessible. Often verse-chorus-verse structure with a clear
hook.
- Audio markers: clean production, prominent vocals, BPM 100-130 typical

#### `alt-pop`
Pop with alternative or indie production choices — less polished, more
distinctive timbres.
- Audio markers: unusual textures, less commercial vocals, indie production

#### `bedroom-pop`
Lo-fi, intimate pop production. Often home-recorded feeling.
- Audio markers: noticeable production imperfection, intimate vocals,
  often quirky melodic choices

#### `synth-pop`
Pop with prominent synthesizers as the primary texture.
- Audio markers: analog or digital synths foregrounded, often 80s-influenced

### Hip-hop and R&B cluster

#### `hip-hop`
Rap-based vocal delivery, beat-driven, often with sampled or programmed
drums.
- Audio markers: rap cadence in lyrics, 808s or programmed drums

#### `trap`
Specifically trap subgenre — triplet hi-hats, 808s, slower BPM (around
70-90 BPM but feeling faster due to hi-hat density).
- Audio markers: triplet hi-hats, sub-heavy 808s

#### `r&b`
Soulful vocal-led, often slower, smooth production. Distinct from pop by
vocal style (melismatic, expressive) and rhythmic feel.
- Audio markers: prominent vocal runs, sensual or smooth groove

### Electronic cluster

#### `electronic`
Catch-all for fragments dominated by electronic production without
clearer subgenre signal.
- Audio markers: synthesized timbres dominant, programmed beats

#### `ambient`
Atmospheric, texture-focused, often without traditional song structure.
- Audio markers: drones, pads, slow evolution, often no beat or sparse beat

#### `lo-fi`
Deliberately degraded production aesthetic. Tape hiss, vinyl crackle, muted
high end.
- Audio markers: deliberate audio artifacts, chill tempo, often instrumental

### Rock cluster

#### `indie-rock`
Guitar-band rock with indie/alternative production choices.
- Audio markers: distorted or jangly guitars, full band, BPM 110-150

#### `punk`
Fast, aggressive, often political or confrontational. Short song forms.
- Audio markers: distorted guitars, fast BPM, raw vocals

#### `rock`
Generic rock — guitar, bass, drums, no strong sub-genre indicator.
- Audio markers: guitar-driven, full-band arrangement

### Other

#### `experimental`
Doesn't fit conventional structures. Often more about sound design than song
form.
- Audio markers: unusual timbres, non-traditional structure, sonic
  experimentation

#### `world-fusion`
Draws on non-Western musical traditions or fuses traditions. Use sparingly
and only when explicit.
- Audio markers: instruments or scales from specific traditions

## How to combine style tags

Maximum 2 tags per fragment. Combinations should be meaningful, not just
piling on adjectives.

**Good combinations** (describe a real point in style space):
- `indie-folk` + `bedroom-pop` → DIY indie folk
- `alt-pop` + `lo-fi` → lo-fi alt-pop (e.g., Clairo-territory)
- `r&b` + `synth-pop` → modern R&B-pop crossover
- `hip-hop` + `r&b` → contemporary hip-hop/R&B blend

**Bad combinations** (incoherent or just adjective stacking):
- `pop` + `indie-rock` → too vague, pick one
- `ambient` + `punk` → real but very unusual; only use with strong evidence
- `electronic` + `pop` → "electronic" is too generic alongside pop; drop one

## When the user references a specific artist

If the user says "I want this to feel like [artist X]", do not put the
artist name in style. Instead:

- Mentally map the artist to the closest 1-2 style tags
- Add the user's reference to `reasoning` field for context

Example:
- User: "I'm going for a Phoebe Bridgers vibe"
- Tags: `style: ["indie-folk"]`
- Reasoning: "Style inferred from user reference to Phoebe Bridgers."

This protects from over-claiming the artist association while preserving
the user's intent for the Producer Agent.

## What is NOT a style tag

These often look like style but aren't:

- **Emotions**: "sad", "happy", "moody" → emotion tag, not style
- **Tempo descriptions**: "slow", "fast", "chill" → not style
- **Adjectives**: "dark", "warm", "bright" → not style
- **Era**: "80s", "90s" → not style (could be `synth-pop` if 80s-like)
- **Production techniques**: "compressed", "wet reverb" → not style
- **Single instruments**: "piano song", "guitar song" → not style

If you find yourself reaching for one of these, leave style empty.

## When to leave style empty (default case)

- Voice memo with humming, no instrumentation → `style: []`
- Text fragment with no audio → `style: []`
- Emoji input → `style: []`
- Very short instrumental fragment with no genre signature → `style: []`
- Ambiguous between 3+ styles → `style: []`

Leaving style empty is the right answer for most fragments. The Producer
Agent does not need style to function. It is a bonus signal when available,
not a requirement.
