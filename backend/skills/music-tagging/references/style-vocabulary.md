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
   - Wall of reverb burying the vocals → shoegaze-leaning
   - Irregular time signatures + angular riffs → math-rock-leaning

3. **Lyric form signals**: The lyrics use a recognizable form:
   - Trap cadence (triplet flows, ad-libs)
   - Ballad structure (long descriptive verses)
   - Hip-hop verse density
   - Blues call-and-response or AAB stanza form
   - Jazz scat syllables or chord-tone-based melody

4. **Clear BPM + key + texture combination**: e.g., 140-150 BPM in minor
   with descriptive verses → indie folk or alt-pop ballad territory;
   12/8 shuffle at 70 BPM with blue notes → blues territory.

When none of these apply → `style: []`.

## Using librosa features for style discrimination

When audio features are available, use these numerical signals as
**supporting evidence** for style assignment. Never assign a style based
on a single feature — combine with what you hear.

### Feature → style mapping

| Feature | Value | Style signal |
|---|---|---|
| `rhythm_complexity` | > 0.20 | math-rock, jazz, fusion, progressive-rock |
| `rhythm_complexity` | 0.08–0.15 | blues shuffle, soul groove, neo-soul |
| `rhythm_complexity` | < 0.05 | four-on-floor (electronic, synth-pop), punk, metal |
| `spectral_flatness` | > 0.15 | shoegaze, ambient, lo-fi (noise-heavy textures) |
| `spectral_flatness` | 0.05–0.15 | indie-rock, post-punk, psychedelic-rock |
| `spectral_flatness` | < 0.03 | clean acoustic (singer-songwriter, acoustic-ballad, jazz) |
| `dynamic_range` | > 5.0 | post-rock, acoustic-ballad (quiet verse → loud climax) |
| `dynamic_range` | 2.0–4.0 | pop, alt-pop, indie-rock, r&b |
| `dynamic_range` | < 2.0 | punk, metal, trap, lo-fi (compressed or consistently loud) |

### Combination patterns

These multi-feature combinations are strong discriminators:

- **Shoegaze**: `spectral_flatness > 0.12` + `energy_mean > 0.05` +
  `brightness > 2000` = wall of sound (not ambient)
- **Ambient**: `spectral_flatness > 0.10` + `energy_mean < 0.03` +
  `onset_density < 1.5` = textural drone (not shoegaze)
- **Math-rock**: `rhythm_complexity > 0.20` + `spectral_flatness < 0.08` +
  `onset_density > 4` = complex rhythms with clean tones
- **Blues**: `rhythm_complexity` 0.08–0.15 + `brightness < 2000` +
  `dynamic_range` 2–4 = shuffle feel with warm tone
- **Punk/metal**: `dynamic_range < 2.0` + `energy_mean > 0.06` +
  `brightness > 2500` = compressed and loud
- **Post-rock**: `dynamic_range > 5.0` + `onset_density < 3` in some
  segments, > 5 in others = crescendo structure
- **Dream-pop**: `spectral_flatness` 0.05–0.12 + `energy_mean < 0.04` +
  `brightness` 1500–2500 = shimmery but gentle

These are heuristics, not rules. Your ears always override the numbers.

## The 35 style tags

These are intentionally broad genre families, not micro-genres. The goal
is to enable useful semantic retrieval and compatibility assessment, not
to be a music encyclopedia. Organized into 9 clusters.

Taxonomy reference: Spotify genre seeds, Every Noise at Once, and
standard music industry classification.

---

### Singer-songwriter cluster

#### `indie-folk`
Acoustic-based, lyric-forward, often introspective. Moderate tempo. Vocal
prominent over sparse instrumentation.
- Audio markers: acoustic guitar or piano lead, moderate dynamics, finger-
  picking or strumming patterns
- Reference points: Phoebe Bridgers, Bon Iver, Sufjan Stevens, Iron & Wine

#### `singer-songwriter`
Generic singer-songwriter feel — acoustic or piano-led, narrative lyrics,
moderate everything. Use when more specific tags don't fit.
- Audio markers: one main instrument + voice, conversational delivery
- Reference points: Taylor Swift (early), Ed Sheeran, Joni Mitchell

#### `acoustic-ballad`
Slow, intimate, often emotional peak in a quiet way. Voice and one
instrument is the typical texture.
- Audio markers: BPM < 80, sparse arrangement, dynamic restraint
- Reference points: Jeff Buckley, Adele (ballads), Sam Smith

---

### Pop cluster

#### `pop`
Bright, catchy, accessible. Often verse-chorus-verse structure with a
clear hook.
- Audio markers: clean production, prominent vocals, BPM 100-130 typical
- Reference points: Dua Lipa, The Weeknd, Taylor Swift (later)

#### `alt-pop`
Pop with alternative or indie production choices — less polished, more
distinctive timbres.
- Audio markers: unusual textures, less commercial vocals, indie
  production quirks
- Reference points: Lorde, Billie Eilish, Glass Animals

#### `bedroom-pop`
Lo-fi, intimate pop production. Often home-recorded feeling.
- Audio markers: noticeable production imperfection, intimate vocals,
  often quirky melodic choices
- Reference points: Clairo (early), Rex Orange County, boy pablo

#### `synth-pop`
Pop with prominent synthesizers as the primary texture.
- Audio markers: analog or digital synths foregrounded, often 80s-
  influenced, programmed drums
- Reference points: Depeche Mode, Chvrches, The 1975

#### `art-pop`
Pop with conceptual ambition and experimental production. Prioritizes
artistic vision over commercial convention. Often features unconventional
song structures, avant-garde sonic textures, or high-concept themes.
- Audio markers: unexpected arrangement choices, genre-blending within a
  single track, theatrical or mannered vocal delivery, complex production
  layers
- Reference points: Björk, Kate Bush, FKA twigs, St. Vincent, Charli XCX
  (later work)
- Spotify genre: "art pop"
- Distinction from `alt-pop`: art-pop has a stronger conceptual or avant-
  garde intent; alt-pop is indie-inflected mainstream pop

#### `dream-pop`
Atmospheric, ethereal, lush — prioritizes mood and texture over lyrical
density. Vocals often blended into the soundscape rather than placed in
front.
- Audio markers: heavy reverb, shimmering guitars or synths, breathy or
  ethereal vocals, moderate tempo, gentle dynamics
- Reference points: Cocteau Twins, Beach House, Mazzy Star, Cigarettes
  After Sex
- Spotify genre: "dream pop"
- Distinction from `shoegaze`: dream-pop is gentler and more melodic;
  shoegaze is louder, denser, and more distorted

---

### Hip-hop, R&B & Soul cluster

#### `hip-hop`
Rap-based vocal delivery, beat-driven, often with sampled or programmed
drums. Covers boom-bap, conscious, lyrical, and general rap styles.
- Audio markers: rap cadence in lyrics, 808s or programmed drums, sampled
  loops or original beats
- Reference points: Kendrick Lamar, J. Cole, Tyler the Creator

#### `trap`
Specifically trap subgenre — triplet hi-hats, 808s, slower BPM (around
70-90 BPM but feeling faster due to hi-hat density).
- Audio markers: triplet hi-hats, sub-heavy 808s, often dark minor keys
- Reference points: Travis Scott, Future, Young Thug, Playboi Carti

#### `r&b`
Contemporary R&B — smooth, often slower, polished production. Distinct
from pop by vocal style (melismatic, expressive) and rhythmic feel.
- Audio markers: prominent vocal runs, sensual or smooth groove, layered
  backing vocals, programmed drums
- Reference points: SZA, Frank Ocean, The Weeknd (R&B side), Daniel Caesar

#### `soul`
Rooted in gospel vocal tradition with secular subject matter. Warmer,
more organic production than modern R&B. Emphasis on vocal power,
live instrumentation, and emotional delivery.
- Audio markers: powerful belting vocals, horn sections, organ, live
  drums with groove emphasis, call-and-response phrasing
- Reference points: Aretha Franklin, Otis Redding, Leon Bridges,
  Alabama Shakes
- Spotify genre: "soul"
- Distinction from `r&b`: soul emphasizes organic instrumentation and
  gospel-rooted vocal delivery; R&B is more production-driven and
  contemporary

#### `neo-soul`
Modern evolution of soul — retains the warmth and vocal focus but adds
hip-hop rhythms, jazz harmony, and electronic textures. Often features
complex chord progressions (7ths, 9ths, altered chords).
- Audio markers: jazzy chords over hip-hop-influenced drums, warm analog
  textures, often uses Fender Rhodes or Wurlitzer, laid-back groove
- Reference points: Erykah Badu, D'Angelo, Anderson .Paak, Hiatus Kaiyote
- Spotify genre: "neo soul"
- Distinction from `soul`: neo-soul is explicitly modern, drawing from
  hip-hop and jazz; classic soul is more traditional

---

### Jazz & Blues cluster

#### `jazz`
Broad jazz tag covering swing, bebop, cool jazz, and modern jazz styles.
Improvisation-based, complex harmony, rhythm section-driven. Use for
fragments with clear jazz vocabulary.
- Audio markers: swing rhythm or complex time feels, extended chord
  voicings (7ths, 9ths, 13ths), walking bass, improvised solo sections,
  brushes on drums
- Reference points: Miles Davis, John Coltrane, Bill Evans, Kamasi
  Washington, Robert Glasper
- Spotify genre: "jazz"
- Note: for jazz-funk or jazz-electronic crossover, use `fusion` instead

#### `blues`
12-bar structure, blue notes, shuffle or straight-8th feels. Emotional
vocal delivery with call-and-response patterns. Can be acoustic (delta/
country blues) or electric (Chicago/Texas blues).
- Audio markers: I-IV-V chord progression, shuffle rhythm (triplet feel),
  bent notes ("blue notes"), pentatonic melodies, AAB lyric form (first
  line repeated, then resolution)
- Reference points: B.B. King, Muddy Waters, Gary Clark Jr., John Mayer
  (blues side)
- Spotify genre: "blues"
- Related Spotify genres: "acoustic blues", "chicago blues", "delta blues",
  "electric blues", "modern blues"

#### `fusion`
Jazz fusion — combines jazz improvisation and harmony with rock, funk,
or electronic elements. Often features virtuosic playing, odd meters,
and extended compositions.
- Audio markers: jazz harmony over rock/funk rhythms, electric guitar and
  keyboards prominent, complex arrangements, often instrumental, odd time
  signatures common
- Reference points: Herbie Hancock (Head Hunters), Pat Metheny, Snarky
  Puppy, Chick Corea
- Spotify genre: "jazz fusion"
- Distinction from `jazz`: fusion explicitly mixes jazz with rock/funk/
  electronic; straight jazz stays within traditional jazz vocabulary

---

### Electronic cluster

#### `electronic`
Catch-all for fragments dominated by electronic production without
clearer subgenre signal.
- Audio markers: synthesized timbres dominant, programmed beats
- Reference points: Aphex Twin, Four Tet, Bonobo

#### `ambient`
Atmospheric, texture-focused, often without traditional song structure.
- Audio markers: drones, pads, slow evolution, often no beat or sparse
  beat, long reverb tails
- Reference points: Brian Eno, Stars of the Lid, Nils Frahm

#### `lo-fi`
Deliberately degraded production aesthetic. Tape hiss, vinyl crackle,
muted high end.
- Audio markers: deliberate audio artifacts, chill tempo, often
  instrumental, jazz-influenced chords
- Reference points: Nujabes, J Dilla (instrumental), lo-fi hip-hop
  playlists

---

### Rock cluster

#### `rock`
Generic rock — guitar, bass, drums, no strong sub-genre indicator.
- Audio markers: guitar-driven, full-band arrangement, BPM 100-150
- Reference points: Foo Fighters, Arctic Monkeys, The Killers

#### `indie-rock`
Guitar-band rock with indie/alternative production choices.
- Audio markers: distorted or jangly guitars, full band, BPM 110-150,
  less polished than mainstream rock
- Reference points: Radiohead, The Strokes, Vampire Weekend, Mac DeMarco

#### `soft-rock`
Melodic, mellow rock with emphasis on vocal harmony and acoustic textures.
Less aggressive than standard rock — bridges rock and pop.
- Audio markers: clean or lightly driven guitars, prominent vocal
  harmonies, moderate dynamics, often piano-driven, BPM 80-120
- Reference points: Fleetwood Mac, Eagles, Elton John, John Mayer
  (pop-rock side)
- Spotify genre: "soft rock"
- Distinction from `acoustic-ballad`: soft-rock has full band arrangement
  (bass, drums, keys); acoustic-ballad is stripped to voice + one instrument

#### `post-rock`
Builds gradually from quiet passages to massive climaxes. Minimal or no
vocals. Emphasizes dynamics, texture, and long-form structure over
traditional verse-chorus.
- Audio markers: crescendo/decrescendo structures, layered guitars with
  heavy delay and reverb, often 5+ minute tracks, minimal or no vocals,
  tremolo picking, orchestral dynamics in a band context
- Reference points: Mogwai, Explosions in the Sky, Godspeed You! Black
  Emperor, Sigur Rós
- Spotify genre: "post-rock"
- Distinction from `ambient`: post-rock has a rock band core (guitars,
  bass, drums) with dynamic arcs; ambient is fully textural

#### `math-rock`
Angular, rhythmically complex rock with irregular time signatures and
intricate interlocking guitar patterns. Often technical but with
melodic sensibility.
- Audio markers: odd time signatures (5/4, 7/8, 11/8), frequent meter
  changes, tapping/fingerpicking guitar techniques, interlocking rhythms,
  clean or lightly distorted guitar tones, complex drum patterns
- Reference points: toe, TTNG, Clever Girl, American Football, Chinese
  Football, Elephant Gym
- Spotify genre: "math rock"
- Distinction from `progressive-rock`: math-rock is usually shorter,
  more angular and minimal; prog-rock is more expansive and orchestral
- Note: librosa BPM detection is unreliable for math-rock due to frequent
  meter changes — set `tempo_compatibility: "unknown"` when math-rock
  style is detected

#### `shoegaze`
Dense wall of guitar distortion and effects, with vocals buried in the
mix. Named for performers staring at their effects pedals.
- Audio markers: massive reverb + distortion layering, vocals mixed low
  and blurred into the texture, tremolo and chorus effects, often
  moderate tempo, dreamy but loud
- Reference points: My Bloody Valentine, Slowdive, Ride, Nothing,
  Kinoko Teikoku
- Spotify genre: "shoegaze"
- Distinction from `dream-pop`: shoegaze is louder, heavier, and more
  distorted; dream-pop is gentler and more ethereal
- Distinction from `ambient`: shoegaze has a rock band structure with
  drums and distorted guitars; ambient is textural without rock elements

#### `psychedelic-rock`
Rock filtered through psychedelic aesthetics — extended jams, unusual
effects, non-linear song structures, mind-expanding intent.
- Audio markers: heavy use of delay, phaser, flanger, wah; extended
  guitar solos or improvisations; drone elements; non-standard song
  structures; often longer tracks
- Reference points: Tame Impala, King Gizzard, Pink Floyd, The Flaming
  Lips, Khruangbin
- Spotify genres: "psychedelic rock", "neo-psychedelic", "psych-rock"
- Distinction from `progressive-rock`: psych-rock emphasizes sonic texture
  and altered consciousness; prog-rock emphasizes compositional complexity

#### `progressive-rock`
Ambitious, compositionally complex rock. Often features extended forms,
concept albums, virtuosic playing, and genre-blending.
- Audio markers: complex song structures (multiple sections, time
  signature changes), extended compositions (5+ minutes), keyboards
  and synths prominent alongside guitars, virtuosic instrumental passages
- Reference points: Radiohead (OK Computer–Kid A era), Tool, King
  Crimson, Porcupine Tree, Dream Theater
- Spotify genres: "progressive rock", "neo-progressive"
- Distinction from `math-rock`: prog-rock is more expansive and orchestral
  with longer forms; math-rock is angular and minimal

---

### Punk cluster

#### `punk`
Fast, aggressive, often political or confrontational. Short song forms.
- Audio markers: distorted guitars, fast BPM (140-200+), raw vocals,
  simple chord progressions, short songs (2-3 min)
- Reference points: Ramones, Sex Pistols, Green Day, PUP

#### `post-punk`
Angular, atmospheric rock emerging from punk's energy but with more
experimentation, darker tones, and art-school sensibilities. Often
features prominent bass, sparse guitar, and deadpan or dramatic vocals.
- Audio markers: driving bass lines (often leading the melody), angular/
  sparse guitar (chorus + delay), programmed or mechanical-sounding drums,
  dark or brooding atmosphere, deadpan or theatrical vocal delivery
- Reference points: Joy Division, Bauhaus, Interpol, Fontaines D.C.,
  Idles, 梅卡德尔 (Chinese post-punk scene)
- Spotify genres: "post-punk", "gothic post-punk", "uk post-punk"
- Distinction from `punk`: post-punk is more atmospheric and experimental;
  punk is faster, simpler, and more aggressive
- Distinction from `indie-rock`: post-punk has a darker, more angular
  sonic identity rooted in punk heritage; indie-rock is broader

---

### Heavy cluster

#### `metal`
Heavy, aggressive music built on distorted guitars, powerful drums, and
often extreme vocal styles. Covers traditional metal, thrash, doom,
black metal, and other subgenres not specific enough for `metalcore`.
- Audio markers: heavily distorted guitars (often drop-tuned), double
  bass drumming, powerful vocals (clean or harsh), riff-driven, high
  volume/intensity, BPM varies widely (doom = 60-80, thrash = 180-220)
- Reference points: Metallica, Black Sabbath, Gojira, Mastodon, Deftones
- Spotify genres: "metal", "heavy metal", "thrash metal", "doom metal",
  "progressive metal", "death metal", "black metal"
- Distinction from `rock`: metal is heavier, more distorted, more extreme
  in dynamics and technique

#### `metalcore`
Fusion of metal's heaviness with hardcore punk's aggression and structure.
Features alternation between screamed/growled and clean vocals, breakdowns,
and high-energy intensity. Covers metalcore, post-hardcore, deathcore,
and hardcore.
- Audio markers: alternating harsh/clean vocals, breakdowns (half-time
  heavy sections), palm-muted chugging riffs, blast beats mixed with
  punk rhythms, often drop-tuned guitars
- Reference points: Bring Me the Horizon, Architects, Converge, Knocked
  Loose, Underoath
- Spotify genres: "metalcore", "melodic metalcore", "post-hardcore",
  "deathcore"
- Distinction from `metal`: metalcore emphasizes the hardcore-punk
  influence (breakdowns, harsh/clean dynamic); metal is more riff-driven
  and traditional

---

### Other

#### `experimental`
Doesn't fit conventional structures. Often more about sound design than
song form. Use as a last resort when the fragment clearly has genre
awareness but doesn't match any other tag.
- Audio markers: unusual timbres, non-traditional structure, sonic
  experimentation, extended techniques
- Reference points: Björk (experimental side), Radiohead (Kid A), Arca,
  Oneohtrix Point Never

#### `world-fusion`
Draws on non-Western musical traditions or fuses multiple traditions. Use
sparingly and only when explicit cultural elements are present.
- Audio markers: instruments or scales from specific traditions, non-
  Western rhythmic patterns, polyrhythmic structures
- Reference points: Tinariwen, Bombino, Anoushka Shankar + electronic
  collaborations

---

## How to combine style tags

Maximum 2 tags per fragment. Combinations should be meaningful, not just
piling on adjectives.

**Good combinations** (describe a real point in style space):
- `indie-folk` + `bedroom-pop` → DIY indie folk
- `alt-pop` + `lo-fi` → lo-fi alt-pop (Clairo territory)
- `r&b` + `synth-pop` → modern R&B-pop crossover
- `hip-hop` + `r&b` → contemporary hip-hop/R&B blend
- `neo-soul` + `jazz` → jazz-influenced neo-soul (Robert Glasper territory)
- `post-rock` + `ambient` → ambient post-rock (Sigur Rós territory)
- `shoegaze` + `dream-pop` → overlap zone (Slowdive territory)
- `blues` + `rock` → blues-rock (Gary Clark Jr. territory)
- `metal` + `progressive-rock` → progressive metal (Tool territory)
- `psychedelic-rock` + `shoegaze` → psych-shoegaze (Spacemen 3 territory)
- `post-punk` + `shoegaze` → darkgaze / dark shoegaze
- `art-pop` + `electronic` → art-electronic (FKA twigs territory)
- `jazz` + `hip-hop` → jazz rap (A Tribe Called Quest territory)

**Bad combinations** (incoherent or redundant):
- `pop` + `indie-rock` → too vague, pick one
- `ambient` + `punk` → contradictory energy (unless very strong evidence)
- `electronic` + `pop` → "electronic" is too generic alongside pop
- `blues` + `trap` → different musical traditions without a clear bridge
- `metal` + `acoustic-ballad` → contradictory intensity
- `soul` + `neo-soul` → redundant; pick the more accurate one

## When the user references a specific artist

If the user says "I want this to feel like [artist X]", do not put the
artist name in style. Instead:

- Mentally map the artist to the closest 1-2 style tags
- Add the user's reference to `reasoning` field for context

**Artist → tag mapping examples**:
- Phoebe Bridgers → `indie-folk`
- Björk → `art-pop` or `experimental`
- Tame Impala → `psychedelic-rock`
- My Bloody Valentine → `shoegaze`
- TTNG / toe → `math-rock`
- Mogwai → `post-rock`
- Joy Division → `post-punk`
- B.B. King → `blues`
- Erykah Badu → `neo-soul`
- Snarky Puppy → `fusion`
- Fleetwood Mac → `soft-rock`
- Beach House → `dream-pop`
- Kendrick Lamar → `hip-hop`
- Travis Scott → `trap`
- Tool → `metal` + `progressive-rock`
- Bring Me the Horizon → `metalcore`
- Robert Glasper → `jazz` or `neo-soul`
- King Gizzard → `psychedelic-rock`
- Fontaines D.C. → `post-punk`
- Kate Bush → `art-pop`
- Pink Floyd → `progressive-rock` or `psychedelic-rock`

## What is NOT a style tag

These often look like style but aren't:

- **Emotions**: "sad", "happy", "moody" → emotion tag, not style
- **Tempo descriptions**: "slow", "fast", "chill" → not style
- **Adjectives**: "dark", "warm", "bright" → not style
- **Era**: "80s", "90s" → not style (could be `synth-pop` if 80s-like)
- **Production techniques**: "compressed", "wet reverb" → not style
- **Single instruments**: "piano song", "guitar song" → not style
- **Micro-genres**: "vaporwave", "witch house", "hyperpop" → too specific;
  use the closest broad tag (`electronic`, `alt-pop`, etc.)

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
