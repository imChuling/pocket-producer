# Genre Conventions

This reference lists typical structural and harmonic conventions for each
style tag used in `music-tagging/references/style-vocabulary.md`.

Use this to:
- Help the Producer Agent suggest next steps consistent with the fragment's
  apparent style ("for indie folk, the next move is typically a verse with
  more specific imagery")
- Validate whether two fragments' styles are compatible (a `trap` chorus
  and an `indie-folk` verse rarely cohabit)

This is descriptive, not prescriptive. Many great songs break conventions.

## Librosa feature fingerprints

Expected ranges for the three niche-style discriminator features. These
help distinguish genres that share similar BPM/key but differ in texture
and rhythm. Values are typical ranges, not hard boundaries.

| Style | rhythm_complexity | spectral_flatness | dynamic_range |
|---|---|---|---|
| math-rock | high (>0.20) | low (<0.05) | medium (2–4) |
| jazz | high (>0.15) | low (<0.04) | medium-high (3–6) |
| fusion | high (>0.15) | low-medium (0.03–0.08) | medium (2–4) |
| progressive-rock | medium-high (0.10–0.20) | medium (0.04–0.10) | medium-high (3–5) |
| blues | medium (0.08–0.15) | low (<0.04) | medium (2–4) |
| soul | medium (0.06–0.12) | low (<0.04) | medium (2–3) |
| neo-soul | medium (0.06–0.12) | low-medium (0.03–0.06) | medium (2–3) |
| shoegaze | low-medium (0.03–0.08) | high (>0.12) | low-medium (1.5–3) |
| dream-pop | low (0.02–0.06) | medium (0.05–0.12) | low-medium (1.5–3) |
| ambient | low (<0.03) | high (>0.10) | low-medium (1–3) |
| post-rock | low→high (varies by section) | medium (0.05–0.12) | very high (>5) |
| punk | low (<0.04) | medium-high (0.06–0.12) | low (<2) |
| post-punk | low (<0.05) | medium (0.05–0.10) | low-medium (1.5–2.5) |
| metal | low (<0.04) | medium-high (0.06–0.12) | low (<2) |
| metalcore | low-medium (0.03–0.08) | medium-high (0.06–0.12) | low-medium (1.5–2.5) |
| trap | low (<0.04) | low-medium (0.03–0.07) | low (<2) |
| lo-fi | low (<0.04) | medium (0.05–0.10) | low (<2) |
| pop | low (<0.05) | low (<0.04) | medium (2–4) |
| indie-rock | low-medium (0.03–0.08) | medium (0.04–0.08) | medium (2–4) |
| acoustic-ballad | low (<0.04) | low (<0.03) | medium-high (3–6) |
| singer-songwriter | low (<0.04) | low (<0.03) | medium (2–4) |

## Style-by-style conventions

### indie-folk

- **Tempo**: 60-100 BPM most common; some up to 120
- **Keys**: often minor or modal (Dorian, Aeolian); sometimes major with
  modal interchange
- **Structure**: usually verse-chorus or verse-pre-chorus-chorus; bridge
  common; outros often instrumental
- **Lyrical density**: high — narrative, specific imagery, particular places
- **Production**: acoustic guitar or piano lead; sparse arrangement; reverb
  moderate; vocal prominent
- **Typical instrumentation**: acoustic guitar, piano, vocal, strings,
  occasional drums (often brushes)

### singer-songwriter

- **Tempo**: 60-110 BPM
- **Keys**: full range; both major and minor common
- **Structure**: classic verse-chorus, often with multiple verses
- **Lyrical density**: high; conversational delivery
- **Production**: voice + one or two instruments; intimate dynamic range
- **Typical instrumentation**: piano OR acoustic guitar as primary; vocal
  central

### acoustic-ballad

- **Tempo**: 60-80 BPM
- **Keys**: any; emotional weight more important than mode
- **Structure**: simple — verse, chorus, possibly bridge; often 3-4 minutes
- **Production**: extreme intimacy; minimal arrangement; vocal in front

### pop

- **Tempo**: 100-130 BPM most common
- **Keys**: major dominant; minor rising in modern pop
- **Structure**: verse-pre-chorus-chorus-verse-pre-chorus-chorus-
  bridge-chorus; 3-3.5 minute target
- **Lyrical density**: moderate; emphasis on hook repetition
- **Production**: polished, full arrangement, prominent vocals, layered
  harmonies

### alt-pop

- **Tempo**: 90-130 BPM
- **Keys**: minor and modal increasingly common; tonal ambiguity acceptable
- **Structure**: pop forms with allowed irregularities (extended bridges,
  unconventional choruses)
- **Production**: distinctive textures over polish; vocal effects and
  processing common

### bedroom-pop

- **Tempo**: 80-130 BPM
- **Keys**: any; often unusual choices
- **Structure**: looser than mainstream pop; can omit standard sections
- **Production**: lo-fi aesthetic intentional; close-mic'd vocals;
  programmed drums or sparse live drums; warm/saturated low end

### synth-pop

- **Tempo**: 100-130 BPM
- **Keys**: often minor with major-key choruses; modal ambiguity common
- **Structure**: classic verse-chorus; instrumental hooks important
- **Production**: synthesizers (analog or digital) as primary instrument;
  programmed drums; gated reverbs

### hip-hop

- **Tempo**: 70-100 BPM (felt) often felt as 140-180 (double time)
- **Keys**: minor dominant; modal scales (Phrygian, harmonic minor)
- **Structure**: verse-hook-verse-hook-verse-hook; 16 bars typical for
  verses
- **Lyrical density**: very high (rap requires syllable density)
- **Production**: programmed drums, samples or original beats, 808s

### trap

- **Tempo**: detected as 70-90 BPM, felt as 140-180 (double time)
- **Keys**: dark minor keys common (Cm, Ebm, F#m)
- **Structure**: verse-hook-verse-hook
- **Lyrical density**: triplet flows, ad-libs, melodic rap
- **Production**: 808 bass, triplet hi-hats, sub bass; reverb on vocals;
  pitched ad-libs

### r&b

- **Tempo**: 70-100 BPM
- **Keys**: minor common; complex chord progressions (7ths, 9ths, 11ths)
- **Structure**: verse-chorus often with extended pre-chorus; bridges
  common
- **Lyrical density**: low to moderate; emphasis on vocal expression
- **Production**: smooth, layered; backing vocals; programmed drums

### electronic

- **Tempo**: 100-140 BPM range broadly
- **Keys**: full range
- **Structure**: often build-drop or build-release rather than verse-chorus
- **Production**: synthesizers and programming central; vocals often
  processed or absent

### ambient

- **Tempo**: often no detectable BPM (drones, slowly evolving textures)
- **Keys**: modal or atonal common; major often peaceful
- **Structure**: through-composed; sections evolve gradually; rarely
  verse-chorus
- **Production**: pads, drones, field recordings; long reverb tails; sparse
  to absent rhythm

### lo-fi

- **Tempo**: 70-100 BPM
- **Keys**: jazz-influenced minor and major; 7ths and 9ths common
- **Structure**: looped or short forms; less defined section boundaries
- **Production**: deliberate tape saturation, vinyl crackle, low-pass
  filter, mono moments; chill production aesthetic

### indie-rock

- **Tempo**: 100-150 BPM
- **Keys**: full range; modal interchange common
- **Structure**: standard verse-chorus-bridge with allowed extensions
- **Production**: distorted or jangly guitars; full band; vocal mid-prominent

### punk

- **Tempo**: 140-200 BPM
- **Keys**: simple major or minor; power-chord-friendly
- **Structure**: short, often 2-3 minutes; verse-chorus-verse-chorus-out
- **Lyrical density**: moderate; direct
- **Production**: distorted guitars, driving bass, prominent drums, raw vocals

### rock

- **Tempo**: 100-150 BPM
- **Keys**: full range
- **Structure**: classic verse-chorus-bridge
- **Production**: full band; balanced mix; vocal in front

### art-pop

- **Tempo**: 80–130 BPM; varies widely by concept
- **Keys**: any; tonal ambiguity and key changes common
- **Structure**: often unconventional — extended intros, irregular section
  lengths, concept-driven sequencing; may follow pop form with subversions
- **Lyrical density**: moderate to high; often theatrical or conceptual
- **Production**: layered, genre-blending; avant-garde textures mixed with
  pop accessibility; heavy use of studio as instrument
- **Typical instrumentation**: synthesizers, strings, processed vocals,
  drum machines; wide variety depending on concept

### dream-pop

- **Tempo**: 80–120 BPM; generally moderate
- **Keys**: any; major and minor both common; tonal vagueness acceptable
- **Structure**: verse-chorus or through-composed; sections bleed into
  each other with long transitions; bridges rare
- **Lyrical density**: low; vocals are part of the texture, not the focus
- **Production**: drenched in reverb; shimmering guitars or synths; gentle
  dynamics; breathy or ethereal vocal treatment; slow attack on most sounds
- **Typical instrumentation**: clean or lightly effected guitar, synth pads,
  subdued drums, layered vocals

### soul

- **Tempo**: 60–120 BPM; slow ballads to uptempo grooves
- **Keys**: major and minor both common; often uses gospel chord movements
  (IV–V–I, plagal cadences)
- **Structure**: verse-chorus with bridge; call-and-response sections;
  sometimes extended outros with vocal ad-libs
- **Lyrical density**: moderate; emphasis on vocal expression over word count
- **Production**: warm, organic; live instrumentation preferred; horn
  sections common; minimal electronic processing
- **Typical instrumentation**: vocals (powerful, belting), organ/piano,
  horns, bass guitar, live drums, occasional strings

### neo-soul

- **Tempo**: 70–110 BPM; generally laid-back groove
- **Keys**: minor common; complex jazz-influenced harmony (7ths, 9ths,
  altered chords); modal interchange frequent
- **Structure**: verse-chorus but with jazz-like harmonic movement;
  extended instrumental sections; vamp-based outros
- **Lyrical density**: low to moderate; laid-back delivery
- **Production**: warm analog textures; Fender Rhodes / Wurlitzer prominent;
  hip-hop-influenced programmed or hybrid drums; subtle vinyl warmth
- **Typical instrumentation**: Rhodes/Wurlitzer, bass (electric or synth),
  drums (programmed or live with hip-hop feel), vocals, occasional horns

### jazz

- **Tempo**: varies widely (ballad 50–70, swing 120–180, bebop 200+)
- **Keys**: all keys; modulation and tonal centers shift frequently;
  extended harmony (7ths, 9ths, 13ths, altered chords) is standard
- **Structure**: head-solos-head (32-bar AABA or 12-bar blues); rhythm
  changes; through-composed for modern jazz
- **Lyrical density**: typically instrumental; vocal jazz features standards
- **Production**: live recording aesthetic; natural room sound; minimal
  processing; dynamics driven by performers
- **Typical instrumentation**: piano/keys, upright or electric bass, drums
  (brushes or sticks), saxophone, trumpet, guitar (jazz voicings)

### blues

- **Tempo**: 60–130 BPM; shuffle feel common
- **Keys**: any; but A, E, G, D particularly common (open guitar keys);
  blue notes (b3, b5, b7) define the sound
- **Structure**: 12-bar blues dominant; AAB lyric form; also 8-bar and
  16-bar variations; turnarounds at end of cycle
- **Lyrical density**: moderate; narrative, often about hardship and emotion
- **Production**: varies from raw acoustic (delta) to full electric band
  (Chicago); tube amp distortion on guitar; live feel preferred
- **Typical instrumentation**: guitar (acoustic or electric), vocals,
  harmonica, bass, drums, sometimes piano and horns

### fusion

- **Tempo**: 80–160 BPM; varies by sub-style
- **Keys**: complex; jazz harmony over non-jazz rhythms; frequent key
  changes and modal shifts; odd meters (5/4, 7/8, 6/8) common
- **Structure**: long-form compositions; head-solo-head adapted for band
  settings; often instrumental; suites and multi-part compositions
- **Lyrical density**: usually instrumental; occasional vocal features
- **Production**: studio or live; electric instruments foregrounded;
  complex arrangements; sometimes electronic textures blended with live
- **Typical instrumentation**: electric guitar, keyboards (Rhodes, synths),
  electric bass (often fretless), drums, sometimes horns or wind instruments

### soft-rock

- **Tempo**: 80–120 BPM; moderate and relaxed
- **Keys**: major dominant; minor for emotional contrast; simple progressions
- **Structure**: classic verse-chorus-bridge; often long instrumental
  sections or extended outros; radio-friendly length
- **Lyrical density**: moderate; melodic vocal delivery with harmonies
- **Production**: clean, warm mix; emphasis on vocal harmony; lightly
  driven or clean guitars; polished but not aggressive
- **Typical instrumentation**: electric and acoustic guitar, piano/organ,
  bass, drums (steady, not complex), prominent backing vocals

### post-rock

- **Tempo**: variable (60–140 BPM); often shifts dramatically within a track
- **Keys**: any; often modal or ambiguous; builds around a tonal center
  rather than strict key
- **Structure**: crescendo-based; quiet-loud-quiet arcs; typically 5–15
  minutes; minimal or no vocals; no traditional verse-chorus
- **Lyrical density**: usually none; instrumental focus
- **Production**: heavy use of delay and reverb; layered guitars; dynamic
  range is extreme (whisper to wall of sound); sometimes orchestral elements
- **Typical instrumentation**: guitars (2-3, heavily effected), bass, drums,
  occasional strings/piano/glockenspiel

### math-rock

- **Tempo**: 100–160 BPM but often misleading due to meter changes; librosa
  BPM detection unreliable
- **Keys**: any; often modal or tonally ambiguous; unusual chord voicings
- **Structure**: through-composed or riff-based sections; frequent meter and
  tempo shifts; typically 3–6 minutes; minimal or no vocals (in Japanese/
  Taiwanese math-rock) or emo-influenced vocals (in Western math-rock)
- **Lyrical density**: low; many tracks are instrumental
- **Production**: clean tones or light distortion; precise, dry recording;
  emphasis on rhythmic clarity; often sparse arrangement despite complexity
- **Typical instrumentation**: guitar (tapping, fingerpicking), bass (often
  melodic), drums (complex patterns, odd time), occasionally keys

### shoegaze

- **Tempo**: 80–130 BPM; generally moderate
- **Keys**: any; often obscured by dense distortion; tonal center may be
  ambiguous
- **Structure**: verse-chorus but blurred; sections flow into each other;
  typically 4–6 minutes; bridges rare
- **Lyrical density**: low; vocals are buried in the mix and function as
  another textural layer
- **Production**: massive reverb + distortion layering; tremolo and chorus
  effects; low-mid-heavy frequency balance; deliberate lo-fi in some cases
- **Typical instrumentation**: heavily effected guitars (multiple layers),
  bass, drums, vocals (mixed low)

### psychedelic-rock

- **Tempo**: 80–140 BPM; can shift within a track
- **Keys**: any; modal scales common (Mixolydian, Dorian); drone-based
  tonality in some styles
- **Structure**: often extended — 5–10+ minutes; improvisatory sections;
  may follow verse-chorus loosely but with long instrumental passages
- **Lyrical density**: variable; can be stream-of-consciousness or minimal
- **Production**: heavy use of effects (delay, phaser, flanger, wah,
  reverse reverb); stereo panning effects; sometimes lo-fi or intentionally
  distorted
- **Typical instrumentation**: guitar (heavily effected), bass, drums,
  keyboards/organ, sitar or other non-Western instruments occasionally

### progressive-rock

- **Tempo**: varies within a single composition (60–180 BPM)
- **Keys**: complex; frequent modulation; extended harmony; odd meters
  (5/4, 7/8, 6/8, 11/8) common
- **Structure**: multi-section suites; concept albums; compositions often
  5–20 minutes; may include distinct movements
- **Lyrical density**: moderate; often narrative or conceptual
- **Production**: high fidelity; complex arrangements; layered; orchestral
  elements blended with rock instrumentation
- **Typical instrumentation**: keyboards/synths (prominent), guitar, bass,
  drums, sometimes mellotron, strings, or brass sections

### post-punk

- **Tempo**: 100–150 BPM; driving and mechanical feel
- **Keys**: minor dominant; dark modal tonality; bass often carries the
  melodic line rather than guitar
- **Structure**: verse-chorus or repetitive / motorik; angular rather than
  flowing; typically 3–5 minutes
- **Lyrical density**: moderate; deadpan, theatrical, or spoken-word delivery
- **Production**: bass-forward mix; angular guitars with chorus + delay;
  mechanical or programmed drums; dark atmosphere; often sparse arrangement
- **Typical instrumentation**: bass (prominent, often leads), guitar (angular,
  effected), drums (mechanical/tight), synths occasionally, vocals
  (deadpan or dramatic)

### metal

- **Tempo**: varies widely by subgenre — doom 60–80 BPM, traditional
  100–140, thrash 160–220
- **Keys**: minor dominant; diminished and chromatic movement; drop tunings
  (Drop D, Drop C, Drop B) standard
- **Structure**: intro-verse-chorus-verse-chorus-solo-chorus-outro;
  often 4–8 minutes; breakdowns in some subgenres
- **Lyrical density**: moderate to high; clean, screamed, or growled
  delivery depending on subgenre
- **Production**: high gain, heavily distorted guitars; tight low end;
  powerful drums (double bass common); often brick-wall mastered
- **Typical instrumentation**: electric guitar (distorted, often dual),
  bass, drums (double kick), vocals; sometimes keyboards for atmosphere

### metalcore

- **Tempo**: 100–180 BPM; frequently shifts between fast sections and
  half-time breakdowns
- **Keys**: minor; drop tunings standard; often moves between tonal
  centers for dynamic contrast
- **Structure**: verse-chorus with breakdowns (half-time heavy sections);
  alternating harsh/clean vocal sections; bridges often feature clean or
  ambient passages; typically 3–5 minutes
- **Lyrical density**: high during screamed sections; moderate in clean
  sections
- **Production**: tight, modern production; heavily compressed guitars;
  triggered or sample-replaced drums; clean vocal sections often heavily
  produced with harmonies
- **Typical instrumentation**: electric guitar (drop-tuned, palm-muted
  chugging), bass, drums (blast beats + grooves), dual vocals (harsh +
  clean)

### experimental

- **Tempo**: any or none
- **Keys**: any, atonal, or absent
- **Structure**: any; often non-narrative
- **Production**: emphasis on sound design over song form

### world-fusion

- Highly variable. Treat as needing user description.

## Style compatibility for relationship-rules

Some style pairs are highly compatible. Others rarely cohabit. Use this when
two fragments have different style tags but might still be one song:

### Compatible style pairs

These can appear in the same song without issue:

- `indie-folk` + `singer-songwriter`
- `acoustic-ballad` + `singer-songwriter`
- `acoustic-ballad` + `indie-folk`
- `pop` + `alt-pop`
- `pop` + `synth-pop`
- `bedroom-pop` + `alt-pop`
- `bedroom-pop` + `lo-fi`
- `hip-hop` + `r&b`
- `hip-hop` + `trap`
- `indie-rock` + `rock`
- `indie-rock` + `alt-pop`
- `dream-pop` + `shoegaze` (Slowdive territory)
- `soul` + `r&b`
- `neo-soul` + `r&b`
- `neo-soul` + `soul`
- `neo-soul` + `jazz`
- `blues` + `rock`
- `blues` + `soul`
- `metal` + `metalcore`
- `punk` + `metalcore`
- `punk` + `post-punk`
- `post-rock` + `ambient`
- `shoegaze` + `indie-rock`
- `psychedelic-rock` + `rock`
- `progressive-rock` + `rock`
- `soft-rock` + `rock`
- `soft-rock` + `pop`
- `art-pop` + `alt-pop`
- `art-pop` + `synth-pop`
- `dream-pop` + `ambient`

### Possible but unusual style pairs

These require deliberate intention:

- `acoustic-ballad` + `electronic` (e.g., Bon Iver later work)
- `r&b` + `electronic` (modern alt-R&B)
- `indie-folk` + `lo-fi`
- `hip-hop` + `synth-pop`
- `jazz` + `hip-hop` (jazz rap — A Tribe Called Quest territory)
- `jazz` + `electronic` (nu-jazz / Jazztronica)
- `blues` + `jazz` (blues-jazz crossover)
- `fusion` + `progressive-rock` (prog-fusion)
- `metal` + `progressive-rock` (progressive metal — Tool territory)
- `psychedelic-rock` + `shoegaze` (psych-shoegaze)
- `post-punk` + `shoegaze` (darkgaze)
- `post-punk` + `synth-pop` (dark synth-pop crossover)
- `art-pop` + `electronic` (FKA twigs territory)
- `dream-pop` + `indie-folk` (atmospheric folk)
- `soul` + `blues` + (soul-blues — already compatible but unusual blend)
- `neo-soul` + `lo-fi` (lo-fi neo-soul production)
- `metalcore` + `electronic` (modern hybrid metalcore)
- `post-rock` + `progressive-rock` (expansive, atmospheric)

### Rarely compatible

These usually indicate different songs:

- `trap` + `indie-folk` (very different genre conventions)
- `punk` + `r&b`
- `ambient` + `pop`
- `experimental` + most others
- `metal` + `acoustic-ballad`
- `metal` + `indie-folk`
- `metalcore` + `dream-pop`
- `trap` + `jazz`
- `blues` + `trap`
- `blues` + `electronic`
- `punk` + `dream-pop`
- `math-rock` + `hip-hop`
- `jazz` + `punk`
- `soul` + `metal`

When two fragments have rarely-compatible styles, the styles alone are not
enough to set `musical_compatibility: conflicting` — but it's evidence in
that direction. Combine with key/tempo signals.

## When style is empty

Most fragments have empty style arrays. In that case, style does not
contribute to musical compatibility evaluation. Use only key and tempo.

This is the common case. Don't over-rely on style for compatibility — it's
the weakest signal of the four because it's the most uncertain to detect.
