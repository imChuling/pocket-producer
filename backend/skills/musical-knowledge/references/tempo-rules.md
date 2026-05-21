# Tempo Rules

This reference defines when two tempos (BPM values) are compatible for the
same song. Used by `relationship-rules` and Producer Agent.

## Foundation: Why tempo matters less than people think

A song's tempo is its heartbeat. Two fragments at radically different tempos
usually feel like different songs.

But songwriters often work at "half time" or "double time" relative to a
song's true feel. A ballad written at 70 BPM might be performed at 140 BPM
"double time" with a faster underlying pulse, or a fast 140 BPM might be
felt at 70 BPM "half time" with the listener's foot tapping the slower
pulse.

For Pocket Producer's purposes, **doubled and halved BPMs are compatible**.
The user is more often the right judge than our detection.

## The four compatibility zones

### Zone 1: Strong compatibility (≤10% difference)

| BPM A | BPM B compatibility range |
|---|---|
| 60 | 54-66 |
| 72 | 65-79 |
| 80 | 72-88 |
| 90 | 81-99 |
| 100 | 90-110 |
| 120 | 108-132 |
| 140 | 126-154 |
| 160 | 144-176 |

Two fragments within these ranges feel like the same tempo. Set
`musical_compatibility: strong` (on tempo dimension).

### Zone 2: Doubled/halved relationship (still strong)

A fragment at 72 BPM and another at 144 BPM can be the same song's idea at
"double time" feel. The product treats these as **strongly compatible**.

The doubled/halved range tolerates ±10% on either:
- 72 + 144 → strong (exactly 2x)
- 72 + 140 → strong (2x within 5%)
- 72 + 150 → strong (2x within 5%)
- 72 + 160 → weak (2x but 11% off — borderline)

To check programmatically:

```
def tempo_compatible(BPM_A, BPM_B):
    # exact-tempo case
    ratio = max(BPM_A, BPM_B) / min(BPM_A, BPM_B)
    if ratio <= 1.10:  # within 10%
        return "strong"

    # doubled/halved case
    doubled = ratio  # already > 1
    if 1.90 <= doubled <= 2.10:
        return "strong"

    # 1.5x relationship
    if 1.40 <= doubled <= 1.60:
        return "weak"

    # within 25%
    if ratio <= 1.25:
        return "weak"

    return "conflicting"
```

### Zone 3: Marginal (10-25% difference, or 1.5x relationship)

Two fragments within 10-25% of each other might be the same song with one
section slowed or rushed (an unusual choice but real songs do this).
Triplet feel against straight feel produces a 3:2 ratio (e.g., 80 vs 120
BPM) — possible but unusual.

Set `musical_compatibility: weak` for these.

### Zone 4: Conflicting (>25% different and not 2x related)

Two fragments at vastly different tempos with no halving/doubling
relationship are different songs.

Examples of conflicting:
- 70 BPM ballad vs 110 BPM mid-tempo (57% apart, not 2x related)
- 90 BPM verse vs 150 BPM chorus (67% apart, not 2x related)

Set `musical_compatibility: conflicting`.

## Special cases

### BPM = 0 or unrecognizable

librosa returns 0 BPM when the audio has no clear rhythmic content
(ambient, drone, free-time piano, sound design). In this case:

- Set `musical_compatibility` based on key alone (if key is detectable)
- If neither tempo nor key is detectable, set `musical_compatibility:
  unknown`

### Very fast or very slow detected tempos

librosa sometimes detects 200+ BPM for a song that humans feel as 100 BPM
(it counted every beat instead of every quarter note). And it detects
40 BPM for songs felt at 80 BPM.

When BPM is below 50 or above 180, treat with caution. Consider the doubled
and halved variants as candidates. If the user's description suggests a
different feel ("slow ballad"), prefer the user's framing.

### Triplet feel vs straight feel

A song in 12/8 time (triplet feel, e.g., classic slow blues) at "60 BPM"
has the same surface pulse as a 4/4 song at 60 BPM, but the underlying
swing is different. Two fragments with the same BPM but different feel may
sound different, but this is too subtle for compatibility judgment at the
agent level. Trust the BPM match.

## How tempo interacts with key

In `relationship-rules`, musical_compatibility is **one signal across both
key AND tempo**. The combined rule:

```
def overall_musical_compatibility(key_compat, tempo_compat):
    # both strong → strong
    if key_compat == "strong" and tempo_compat == "strong":
        return "strong"

    # one strong, other weak → weak
    if {key_compat, tempo_compat} == {"strong", "weak"}:
        return "weak"

    # both weak → weak
    if key_compat == "weak" and tempo_compat == "weak":
        return "weak"

    # any conflicting → conflicting
    if "conflicting" in (key_compat, tempo_compat):
        return "conflicting"

    # any unknown → unknown
    if "unknown" in (key_compat, tempo_compat):
        return "unknown"

    return "weak"  # default fallback
```

A simple rule of thumb: **the weaker signal dominates**.

## When tempo doesn't apply

- Fragment is pure text → tempo not applicable → consider key alone, or set
  `musical_compatibility: n/a` if both fragments are text
- Fragment is ambient/drone with no rhythmic content (BPM = 0) → treat as
  rhythmically open; key compatibility alone decides

## Common songwriter workflow nuances

These don't change the rules but are useful context for the Producer Agent
when explaining decisions to users:

- **"Bedroom ballad" tempos**: 60-80 BPM. Many singer-songwriter fragments
  fall here.
- **"Walking" mid-tempo**: 90-110 BPM. Versatile range; many ballads and
  mid-tempo pop sit here.
- **"Dance" tempos**: 120-128 BPM. Pop, indie-pop, four-on-the-floor.
- **"Driving" rock/indie rock**: 130-150 BPM. Upbeat indie, alt-rock.
- **"Trap" tempos**: detected as 70-90 BPM (half time) but felt as 140-180.
  These are often double-time felt as half-time, which is why doubled/halved
  compatibility matters.

If two fragments fall in **different categories** (e.g., one is bedroom
ballad, one is driving rock) AND they're not in a doubled/halved
relationship, they're likely different songs even if their detected BPMs
happen to be within 25%.
