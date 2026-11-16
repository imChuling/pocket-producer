"""Controlled perturbations of a target stem.

A target is stored as a padded excerpt: MARGIN_BEFORE seconds of lead-in, the
WINDOW_SECONDS window that is aligned with the context, then MARGIN_AFTER
seconds of tail. The padding lets time shifts and time stretches read real
audio from the stem instead of silence.

Each perturbation has a kind:

- directional: by construction the result fits the context worse than the
  original (a semitone transposition, a tempo change), so a compatibility
  scorer should prefer the original;
- invariance: the result fits exactly as well (gain, polarity), so the score
  should not move;
- control: a round trip through the same signal processing as a directional
  perturbation that lands back on the original pitch or tempo. It measures
  how much of a score change is processing artefacts;
- exploratory: no pass or fail expectation, reported as a response curve.

Beat shifts delay the target by a number of the context's beats. Key, tempo,
timbre and pitch-class content stay exactly as they were; only where the
part sits against the context changes.

Pitch and tempo changes use a phase vocoder, which smears transients. The
varispeed family changes both at once by resampling alone, so it is the
directional test that carries no processing artefacts.
"""

from dataclasses import dataclass

import numpy as np

WINDOW_SECONDS = 10.0
# Room to read real audio for a delay of up to one bar at 54 BPM.
MARGIN_BEFORE = 4.5
MARGIN_AFTER = 1.5

PITCHED_ONLY_FAMILIES = frozenset({"pitch", "pitch_roundtrip"})


@dataclass(frozen=True)
class Perturbation:
    name: str
    kind: str
    family: str
    value: float


def catalogue() -> list[Perturbation]:
    items: list[Perturbation] = []
    for semitones in (-6, -3, -2, -1, 1, 2, 3, 6):
        items.append(Perturbation(f"pitch{semitones:+d}", "directional", "pitch", semitones))
    for semitones in (7, 12):
        items.append(Perturbation(f"pitch{semitones:+d}", "exploratory", "pitch", semitones))
    for percent in (-12, -6, -3, 3, 6, 12):
        items.append(
            Perturbation(f"tempo{percent:+d}%", "directional", "tempo", 1.0 + percent / 100.0)
        )
    for semitones in (-2, -1, 1, 2):
        items.append(
            Perturbation(f"varispeed{semitones:+d}", "directional", "varispeed", semitones)
        )
    # Delays in beats of the context. 0.37 of a beat lands between sixteenths;
    # whole beats keep the part on the grid and move its chord changes.
    for beats in (0.37, 0.5, 1, 2, 4):
        items.append(Perturbation(f"beatshift{beats:g}", "directional", "beatshift", beats))
    items.append(Perturbation("gain-6dB", "invariance", "gain", 0.5))
    items.append(Perturbation("polarity", "invariance", "polarity", -1.0))
    items.append(Perturbation("pitch_roundtrip", "control", "pitch_roundtrip", 1.0))
    items.append(Perturbation("tempo_roundtrip", "control", "tempo_roundtrip", 1.06))
    return items


def padded_length(sample_rate: int) -> int:
    return int(round((MARGIN_BEFORE + WINDOW_SECONDS + MARGIN_AFTER) * sample_rate))


def window_length(sample_rate: int) -> int:
    return int(round(WINDOW_SECONDS * sample_rate))


def _fit(audio: np.ndarray, length: int) -> np.ndarray:
    if audio.shape[0] >= length:
        return audio[:length]
    return np.pad(audio, (0, length - audio.shape[0]))


def original(padded: np.ndarray, sample_rate: int) -> np.ndarray:
    start = int(round(MARGIN_BEFORE * sample_rate))
    return padded[start : start + window_length(sample_rate)]


def applicable(perturbation: Perturbation, pitched: bool, beat_seconds: float | None) -> bool:
    """Whether a perturbation means anything for this target."""
    if perturbation.family in PITCHED_ONLY_FAMILIES:
        return pitched
    if perturbation.family == "beatshift":
        return beat_seconds is not None and perturbation.value * beat_seconds <= MARGIN_BEFORE
    return True


def apply(
    perturbation: Perturbation,
    padded: np.ndarray,
    sample_rate: int,
    beat_seconds: float | None = None,
) -> np.ndarray:
    """Return the perturbed window, the same length as the original window.

    `beat_seconds` is the context's beat period; only beat shifts need it.
    """
    import librosa

    padded = np.asarray(padded, dtype=np.float32)
    start = int(round(MARGIN_BEFORE * sample_rate))
    length = window_length(sample_rate)
    family, value = perturbation.family, perturbation.value

    if family == "pitch":
        shifted = librosa.effects.pitch_shift(padded, sr=sample_rate, n_steps=value)
        return shifted[start : start + length]
    if family == "pitch_roundtrip":
        up = librosa.effects.pitch_shift(padded, sr=sample_rate, n_steps=value)
        back = librosa.effects.pitch_shift(up, sr=sample_rate, n_steps=-value)
        return back[start : start + length]
    if family == "tempo":
        # Stretch from the window start so both versions begin together and
        # drift apart afterwards.
        stretched = librosa.effects.time_stretch(padded[start:], rate=value)
        return _fit(stretched, length)
    if family == "tempo_roundtrip":
        there = librosa.effects.time_stretch(padded[start:], rate=value)
        back = librosa.effects.time_stretch(there, rate=1.0 / value)
        return _fit(back, length)
    if family == "varispeed":
        # Tape-style speed change by plain resampling: pitch and tempo move
        # together and there is no time-frequency processing to leave traces.
        speed = 2.0 ** (value / 12.0)
        faster = librosa.resample(
            padded[start:], orig_sr=sample_rate, target_sr=sample_rate / speed
        )
        return _fit(faster, length)
    if family == "beatshift":
        # A pure delay read from the stem itself: no splice, no processing.
        shift = int(round(value * beat_seconds * sample_rate))
        return _fit(padded[start - shift :], length)
    if family == "gain":
        return original(padded, sample_rate) * value
    if family == "polarity":
        return -original(padded, sample_rate)
    raise ValueError(f"unknown perturbation family: {family}")
