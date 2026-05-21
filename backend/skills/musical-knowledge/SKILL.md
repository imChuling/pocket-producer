---
name: musical-knowledge
description: |
  Provides objective music theory rules for evaluating compatibility between
  fragments. Used primarily by relationship-rules and Producer Agent to
  determine whether two fragments can plausibly belong to the same song
  based on key compatibility, tempo relationships, and structural conventions.
  This skill is descriptive of established music theory; it does not generate
  musical content.
license: Apache-2.0
---

# Musical Knowledge

You are providing music theory facts that other skills and agents can consult
to make compatibility judgments. This skill is **purely referential** — it
does not act on fragments. It answers questions like:

- "Are Am and Cm compatible keys?"
- "Are 72 BPM and 144 BPM the same musical idea?"
- "What chord progression conventions does indie folk follow?"

The answers here are based on Western tonal music theory. They are
approximate and conventional, not mathematically perfect. Many great songs
break these rules. Use this skill as a default expectation, not a hard
constraint.

## When to use this skill

Use this skill when:

1. The `relationship-rules` skill asks you to evaluate
   `musical_compatibility` between two fragments.
2. The Producer Agent is generating a next-step suggestion that involves
   musical specifics (e.g., "try this in Am" or "this could be a chorus
   continuation in the relative major").
3. You need to explain a musical decision to the user in plain language.

Do NOT use this skill when:
- Both fragments are pure text (musical compatibility is not applicable)
- Audio features are missing or unreliable
- The question is about emotion or theme (those have their own taxonomies)

## What this skill provides

Three reference documents:

- `references/key-compatibility.md` — How to evaluate whether two keys are
  compatible for a single song.
- `references/tempo-rules.md` — How to evaluate whether two BPMs are
  compatible.
- `references/genre-conventions.md` — Typical structural and harmonic
  conventions for the main style tags used elsewhere in the system.

Load only the reference you need. They are independent.

## Core principle: Compatibility, not correctness

A song "in Am" can move through Cm, F, G, and back to Am without leaving
the listener's sense of "this is one song". Two fragments with different
keys may still belong to the same song if their keys are compatible.

Conversely, two fragments in the exact same key may not belong to the same
song if their tempos or feels are fundamentally different.

**Compatibility = "could these coexist in a single piece of music without
sounding jarring"**, not "do these have identical features".

## Quick lookup table: Key compatibility

For common usage, here is the highest-priority lookup. For the full theory
see `references/key-compatibility.md`.

| Key A | Strongly compatible with |
|---|---|
| C | Am (rel min), G (dom), F (subdom), Cm (parallel) |
| G | Em (rel min), D (dom), C (subdom), Gm (parallel) |
| D | Bm (rel min), A (dom), G (subdom), Dm (parallel) |
| A | F#m (rel min), E (dom), D (subdom), Am (parallel) |
| E | C#m (rel min), B (dom), A (subdom), Em (parallel) |
| F | Dm (rel min), C (dom), Bb (subdom), Fm (parallel) |
| Bb | Gm (rel min), F (dom), Eb (subdom), Bbm (parallel) |
| Am | C (rel maj), Dm (subdom), Em (dom), A (parallel) |
| Em | G (rel maj), Am (subdom), Bm (dom), E (parallel) |
| Dm | F (rel maj), Gm (subdom), Am (dom), D (parallel) |
| Bm | D (rel maj), Em (subdom), F#m (dom), B (parallel) |
| F#m | A (rel maj), Bm (subdom), C#m (dom), F# (parallel) |
| Cm | Eb (rel maj), Fm (subdom), Gm (dom), C (parallel) |
| Gm | Bb (rel maj), Cm (subdom), Dm (dom), G (parallel) |

If both keys are in the same row's "strongly compatible" list, set
`musical_compatibility: strong`.

If one is in the other's "marginal" zone (a fifth away in either direction
that's not in the strong list), set `marginal`.

Otherwise → `conflicting`.

## Quick lookup table: BPM compatibility

| BPM A | BPM B | Compatibility |
|---|---|---|
| 72 | 72 ± 4 | strong (within 5%) |
| 72 | 72 ± 7 | strong (within 10%) |
| 72 | 72 ± 18 | weak (within 25%) |
| 72 | 144 (or 36) | strong (doubled/halved) |
| 72 | 108 (or 48) | weak (1.5x relationship — possible but unusual) |
| 72 | 100+ different | conflicting |

The 5%, 10%, 25% thresholds map to:
- 5% → "imperceptible difference, definitely same tempo intent"
- 10% → "could be the same song at slightly different feels"
- 25% → "could work but requires intentional contrast"
- Beyond 25% (and not in halved/doubled relationship) → different songs

## Note for AI agents

When evaluating musical compatibility:

1. Always read BOTH key AND tempo. A match on one and conflict on the other
   is **conflicting overall**, not "partial match".

2. Trust the librosa-detected key/BPM unless there's strong reason to doubt
   it. The product uses librosa as the objective signal layer; respect it.

3. If you find yourself reasoning about chord progressions or modal
   interchange, you've gone too deep. This skill provides defaults. For
   anything complex, return `marginal` and let the user judge.

4. Do not generate musical content (chord progressions, melodies, riffs) on
   the basis of this knowledge. This skill is descriptive only. Generation
   is out of Pocket Producer's scope.
