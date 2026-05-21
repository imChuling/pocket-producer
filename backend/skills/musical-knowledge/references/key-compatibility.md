# Key Compatibility

This reference defines when two musical keys can plausibly coexist within a
single song. It is used by `relationship-rules` and Producer Agent to
evaluate whether two fragments with different detected keys could belong to
the same piece.

## Foundation: Why keys matter for fragment compatibility

A "key" is the tonal center of a piece of music — the note that feels like
"home". Two fragments in radically different keys typically don't feel like
one song unless there's an intentional modulation between them.

But this is not absolute. Many songs change keys (the Beatles' "Penny
Lane", Whitney Houston's "I Will Always Love You", countless others). Some
keys move into each other more naturally than others.

The classifications below describe **default expectations** for songwriter
fragments. They are not rules of music theory — they are expectations about
what feels coherent without explicit transition.

## The three categories

### Strongly compatible: same song without effort

Two fragments in these key relationships can sit next to each other without
the user needing to write a transition. They feel like one song's natural
variation.

The four core relationships:

1. **Same key.** Am with Am. Self-evident.

2. **Relative major/minor.** Every major key shares notes with its relative
   minor (and vice versa). They have the same key signature.
   - C major ↔ A minor
   - G major ↔ E minor
   - D major ↔ B minor
   - A major ↔ F# minor
   - E major ↔ C# minor
   - F major ↔ D minor
   - Bb major ↔ G minor

3. **Parallel major/minor.** Same root note, different mode.
   - C major ↔ C minor
   - A major ↔ A minor
   - etc.
   Common in songwriting for verse-chorus contrast.

4. **Fifth away (circle of fifths neighbors).** Adjacent in the circle of
   fifths.
   - C ↔ G (or C ↔ F)
   - G ↔ D
   - D ↔ A
   - A ↔ E
   - Am ↔ Em
   - Em ↔ Bm
   - etc.

For `relationship-rules` purposes, **any of these four** counts as
`musical_compatibility: strong`.

### Marginal: possible but needs intentional handling

These can work in one song but usually require a transition or a deliberate
modulation. Songwriters use these for choruses lifting energy, bridges
creating contrast, etc.

- Whole step up or down (C ↔ D, Am ↔ Bm)
- Minor third up or down (C ↔ Eb, C ↔ A)
- Tritone-related (this is more advanced and rarely natural)

For `relationship-rules`, set `musical_compatibility: weak` for these.

### Conflicting: different songs

Two keys far apart in the circle of fifths AND not related by parallel /
relative major-minor. Examples:

- F# and C (tritone apart, distantly related)
- E and Bb (tritone)
- B and F (tritone)
- A and Eb

For `relationship-rules`, set `musical_compatibility: conflicting`.

## The complete reference table

For each key, here are its **strongly compatible** partners:

### Major keys

| Key | Same | Relative minor | Fifth up | Fifth down | Parallel minor |
|---|---|---|---|---|---|
| C | C | Am | G | F | Cm |
| G | G | Em | D | C | Gm |
| D | D | Bm | A | G | Dm |
| A | A | F#m | E | D | Am |
| E | E | C#m | B | A | Em |
| B | B | G#m | F# | E | Bm |
| F# | F# | D#m | C# | B | F#m |
| F | F | Dm | C | Bb | Fm |
| Bb | Bb | Gm | F | Eb | Bbm |
| Eb | Eb | Cm | Bb | Ab | Ebm |
| Ab | Ab | Fm | Eb | Db | Abm |
| Db | Db | Bbm | Ab | Gb | C#m |

### Minor keys

| Key | Same | Relative major | Fifth up | Fifth down | Parallel major |
|---|---|---|---|---|---|
| Am | Am | C | Em | Dm | A |
| Em | Em | G | Bm | Am | E |
| Bm | Bm | D | F#m | Em | B |
| F#m | F#m | A | C#m | Bm | F# |
| C#m | C#m | E | G#m | F#m | C# |
| G#m | G#m | B | D#m | C#m | G# |
| Dm | Dm | F | Am | Gm | D |
| Gm | Gm | Bb | Dm | Cm | G |
| Cm | Cm | Eb | Gm | Fm | C |
| Fm | Fm | Ab | Cm | Bbm | F |
| Bbm | Bbm | Db | Fm | Ebm | Bb |
| Ebm | Ebm | Gb | Bbm | Abm | Eb |

## How to use this table programmatically

For two keys `K1` and `K2`:

```
def keys_compatible(K1, K2):
    if K1 == K2:
        return "strong"  # same key

    # check relative major/minor
    if are_relative(K1, K2):
        return "strong"

    # check parallel
    if are_parallel(K1, K2):
        return "strong"

    # check fifth relationship
    if are_fifth_apart(K1, K2):
        return "strong"

    # check whole step or minor third
    if are_whole_step_apart(K1, K2):
        return "weak"
    if are_minor_third_apart(K1, K2):
        return "weak"

    # otherwise
    return "conflicting"
```

## Edge case: librosa estimated key is ambiguous

librosa's key detection is approximate — it usually gets within a perfect
fifth of the true key, but can confuse:
- Major with its relative minor (Am detected as C, or vice versa)
- Keys with similar chord palettes

When evaluating compatibility, **treat detected keys with some tolerance**:

If `K1` is detected as Am, and `K2` is detected as C, treat as strongly
compatible regardless (they could be the same key, librosa just guessed
which one is more prominent).

In practice, this means: relative major/minor pairs should almost always be
considered the same key for compatibility purposes.

## When to escalate to "user knows best"

If the user has explicitly typed key information in their fragment metadata
or description (e.g., "I wrote this in F# Dorian"), trust the user over
librosa. Modal scales (Dorian, Phrygian, Lydian, etc.) are not directly
covered by this table, but they map to a parent key:

- F# Dorian → parent key A major
- D Phrygian → parent key Bb major
- C Lydian → parent key G major
- A Mixolydian → parent key D major

For compatibility purposes, treat modal keys as their parent.

## When in doubt

Set `marginal`. Conservatively, when in doubt:
- If the keys are within 2 steps in the circle of fifths → marginal
- If further → conflicting
- The user can override your judgment manually

Never set `strong` unless one of the four core relationships clearly holds.
