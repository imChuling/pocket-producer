# Structure Hints

A structure hint suggests **where this fragment might live** in a finished
song. It is one of the most useful signals for the Producer Agent because
it tells the downstream system whether a fragment is a verse seed, a chorus
candidate, a hook, or just a wandering motif.

This is **a suggestion, not a commitment**. The user can always override or
move the fragment elsewhere. The hint helps the Producer Agent suggest
sensible next steps (e.g., "pair this verse_candidate with that chorus
candidate").

## The 7 structure hint values

| Value | Meaning |
|---|---|
| `melodic_motif` | A short instrumental or hummed idea, not yet attached to lyrics or structure |
| `lyric_fragment` | A line or two of lyrics, no clear structural role |
| `verse_candidate` | Looks like material for a verse — narrative, building, scene-setting |
| `chorus_candidate` | Looks like material for a chorus — memorable, emotionally peaked, repeatable |
| `hook_candidate` | A very short, distinctive phrase or melodic figure with strong identity |
| `bridge_candidate` | Looks like material for a bridge — contrast, departure, perspective shift |
| `near_complete_demo` | A multi-section recording where verse + chorus (or more) are present |

You may also set this to `null` when no structural role is reasonably
inferable.

## How to choose

Walk through these rules in order. Stop at the first one that matches.

### Rule 1: Audio with multiple sections → `near_complete_demo`

If the input is audio longer than 60 seconds AND the transcript or audio
features suggest distinct sections (e.g., a verse-like opening followed by
a chorus-like peak), this is `near_complete_demo`.

Hints in transcript:
- Two clearly different lyrical units (verse-like + chorus-like)
- Repetition of a memorable phrase (likely the chorus)
- Section labels in the user's notes ("[verse 1]", "[chorus]")

Hints in audio features:
- Duration > 60s, especially > 120s
- Significant dynamic range across the recording

### Rule 2: Short, distinctive, memorable → `hook_candidate`

Use `hook_candidate` for:
- Audio: < 12 seconds, with a clear memorable melodic figure
- Text: a single line that is short, distinctive, and could be repeated as
  a song's central memorable phrase
- Either: features that make this stand out — wordplay, rhythmic distinctiveness,
  unusual phrase, anchor word

Examples:
- "I keep waiting for the rain to stop, but the rain is me" (text)
- 8-second piano figure with a clear repeating motif (audio)

A hook is not just a chorus. A hook is the **most distinctive 4-10 second
unit** of a potential song. Many songs have a hook that lives inside the
chorus, but a hook can also be an instrumental signature or a recurring
lyric phrase.

### Rule 3: Memorable, emotionally peaked, repeatable → `chorus_candidate`

Use `chorus_candidate` when the fragment has:
- Emotional peak (the strongest emotional moment of the surrounding context)
- Repetition or structure that invites repetition
- A clear "title-like" feel (the line that would be in capital letters on
  the lyric sheet)
- Audio: sustained energy, fuller arrangement, climactic shape

Difference from `hook_candidate`:
- A hook is small and specific (a phrase, a figure)
- A chorus is larger (a section of 4-8 lines or 15-30 seconds of audio)

A chorus can *contain* a hook. They overlap.

### Rule 4: Narrative, building, sets a scene → `verse_candidate`

Use `verse_candidate` when:
- Text: descriptive, narrative, builds context. Multiple lines of related
  but not repeating content. Specific imagery.
- Audio: medium-length (20-60 seconds), moderate dynamics, lyrical density
- Lyrically, verse material often has more syllables per line and more
  specific detail than chorus material

Verses *describe*. Choruses *declare*. If the fragment is describing,
narrating, or scene-setting, it's a verse seed.

### Rule 5: Contrast, departure, perspective shift → `bridge_candidate`

Use `bridge_candidate` when:
- The fragment feels like a *break* from a song's main material
- It introduces a contrast: new perspective, new tonal center, new dynamic
- Often: addresses the listener directly, shifts to second person, reveals
  something not said before
- Lyrically, often the *most emotionally raw* part of a fragment

Audio markers:
- A modulation (key change) compared to the surrounding context
- A sudden dynamic shift (quieter or louder)
- A pre-chorus-like build (though strict pre-choruses are usually tagged
  as part of verse or chorus rather than separately)

### Rule 6: Lyrics with no clear role → `lyric_fragment`

If the input is text but doesn't have any of the markers above (not hook-like,
not chorus-like, not verse-like), it's a `lyric_fragment`. This is common
for short notes, journal-style entries, or single floating lines.

Examples:
- "Something about how mornings used to smell different"
- "Maybe a song about the bus driver"
- "I wrote down the word 'undertow' on a napkin"

### Rule 7: Audio without lyrics, no clear role → `melodic_motif`

Pure instrumental fragments (humming, piano, guitar) that don't fit
`hook_candidate` go here. This is the default for short instrumental ideas
without clear structural identity.

If audio features suggest a distinctive memorable shape → consider
`hook_candidate` instead.

### Rule 8: When in doubt → `null`

Setting `structure_hint: null` is acceptable and often correct. It tells the
Producer Agent "I have no confident guess about where this belongs." That is
useful information — better than a wrong guess.

Common cases for `null`:
- Single emoji input
- Pure mood description with no content ("feeling weird today")
- Very abstract or experimental fragments

## Worked examples

### Example A
Input: 8-second piano recording at 72 BPM in A minor, no vocals.
→ `melodic_motif` (short, instrumental, no distinctive hook quality)

### Example B
Input: 6-second recording, "I keep waiting for the rain to stop, but the
rain is me", sung over single chord.
→ `hook_candidate` (short, distinctive, memorable phrase with strong identity)

### Example C
Input: 35-second voice memo with three lines of descriptive lyrics about
walking through a city at night.
→ `verse_candidate` (narrative, scene-setting, medium length)

### Example D
Input: 4 lines repeating "I won't sleep tonight" over an emotional vocal
delivery and building dynamics.
→ `chorus_candidate` (repetition, emotional peak)

### Example E
Input: Text note: "Maybe a counter-melody where she answers the question
he asked in verse 2."
→ `bridge_candidate` (perspective shift, departure from main material)

### Example F
Input: 2-minute recording with a soft verse-like opening followed by a
louder section with a repeating phrase.
→ `near_complete_demo` (multiple sections in one recording)

### Example G
Input: Text note: "I should write something about my brother."
→ `lyric_fragment` (text with no clear structural role; could become anything)

### Example H
Input: Single emoji: 🌧️
→ `null` (no structural role inferable from emoji alone)

## Common mistakes to avoid

1. **Don't guess `chorus_candidate` for everything emotional.** Many strong
   emotional fragments are verses. Choruses are specifically *repeatable*
   peaks, not just emotional moments.

2. **Don't use `near_complete_demo` for any audio longer than 60 seconds.**
   It must have *multiple distinct sections*. A 2-minute single-section
   verse is still `verse_candidate`.

3. **Don't use `hook_candidate` for any short fragment.** A hook is short
   AND distinctive AND memorable. A short, mumbled humming line is
   `melodic_motif`.

4. **Don't set this based on user labels alone.** If the user said "this is
   my chorus", consider it strongly but verify the fragment has chorus-like
   features. If not, use the technically correct hint and note the user's
   intent in your `reasoning`.

5. **Don't choose based on what you wish the fragment were.** A wandering
   piano improvisation with no structure is `melodic_motif`, even if the
   user clearly wants it to become a chorus eventually.
