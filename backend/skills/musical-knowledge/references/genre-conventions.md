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
- `lo-fi` + `bedroom-pop`
- `hip-hop` + `r&b`
- `hip-hop` + `trap`
- `indie-rock` + `rock`
- `indie-rock` + `alt-pop`

### Possible but unusual style pairs

These require deliberate intention:

- `acoustic-ballad` + `electronic` (e.g., Bon Iver later work)
- `r&b` + `electronic` (modern alt-R&B)
- `indie-folk` + `lo-fi`
- `hip-hop` + `synth-pop`

### Rarely compatible

These usually indicate different songs:

- `trap` + `indie-folk` (very different genre conventions)
- `punk` + `r&b`
- `ambient` + `pop`
- `experimental` + most others

When two fragments have rarely-compatible styles, the styles alone are not
enough to set `musical_compatibility: conflicting` — but it's evidence in
that direction. Combine with key/tempo signals.

## When style is empty

Most fragments have empty style arrays. In that case, style does not
contribute to musical compatibility evaluation. Use only key and tempo.

This is the common case. Don't over-rely on style for compatibility — it's
the weakest signal of the four because it's the most uncertain to detect.
