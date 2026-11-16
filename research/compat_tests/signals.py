"""Clip features and the compatibility scorers under test.

Every scorer is the product's own code path where one exists: the MS-CLAP
adapter, `tempo_match` and `key_match`, the deployed chroma probe's scoring
and the deployed fusion weights. Tempo and key are estimated the way the
ingest pipeline does it (`backend/tools/audio_features.py`).
"""

import json
import pathlib
import sys
from dataclasses import dataclass, field

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ranking.features import key_match, tempo_match  # noqa: E402
from ranking.harmonic_probe import transpose_invariant_score  # noqa: E402

from . import beatgrid, progression  # noqa: E402

KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MAJOR = np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1])
_MINOR = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0])
ONSET_SUBDIVISIONS = 8

# The embedding the product serves; the others are comparison points.
PRODUCT_MODEL = "msclap"
MODEL_NAMES = ("msclap", "laion", "cocola")

SCORER_NAMES = [
    "clap_cos_mix",
    "clap_cos_mean",
    "clap_cos_max",
    "laion_cos_mix",
    "cocola",
    "tempo",
    "key_exact",
    "key_fifth",
    "harmonic_transpose_invariant",
    "chroma_as_is",
    "fusion5_online",
    "fusion5_with_key",
    "chroma_beat_aligned",
    "progression_search",
    "rhythm_on_grid",
    "onset_pattern",
]


@dataclass
class ClipFeatures:
    embeddings: dict[str, np.ndarray] = field(default_factory=dict)
    bpm: float | None = None
    key: str | None = None
    chroma: list[float] = field(default_factory=lambda: [0.0] * 12)
    # Sampled on the context's beat grid; None when the context has no grid.
    beat_chroma: np.ndarray | None = None
    onsets: np.ndarray | None = None


class Embedders:
    """The embedding models, loaded on first use."""

    def __init__(self, names: tuple[str, ...] = MODEL_NAMES):
        self.names = tuple(names)
        self._loaded: dict = {}

    def _get(self, name: str):
        if name not in self._loaded:
            if name == "msclap":
                from ranking.adapters.msclap import MsClapAdapter

                self._loaded[name] = MsClapAdapter()
            elif name == "laion":
                from ranking.research.adapters.laion_clap import LaionClapMusicAdapter

                self._loaded[name] = LaionClapMusicAdapter()
            elif name == "cocola":
                from .cocola_scorer import CocolaScorer

                self._loaded[name] = CocolaScorer()
            else:
                raise ValueError(f"unknown model: {name}")
        return self._loaded[name]

    def encode(self, audio: np.ndarray, sample_rate: int, only=None) -> dict[str, np.ndarray]:
        out = {}
        for name in self.names if only is None else only:
            model = self._get(name)
            if name == "cocola":
                out[name] = model.embed(audio, sample_rate).numpy().astype(np.float32)
            else:
                out[name] = np.asarray(model.encode_audio(audio, sample_rate), dtype=np.float32)
        return out

    def cocola_score(self, context: np.ndarray, candidate: np.ndarray) -> float:
        import torch

        return self._get("cocola").score(torch.from_numpy(context), torch.from_numpy(candidate))


def tempo_key(clip: beatgrid.Frames) -> tuple[float | None, str | None]:
    """Tempo and key as the ingest pipeline estimates them."""
    import librosa

    tempo_raw, _ = librosa.beat.beat_track(y=clip.audio, sr=beatgrid.SAMPLE_RATE)
    tempo = float(np.mean(tempo_raw))
    chroma_mean = clip.chroma.mean(axis=1).astype(np.float64)
    index = int(chroma_mean.argmax())
    rolled = np.roll(chroma_mean, -index)
    major = float(np.corrcoef(rolled, _MAJOR)[0, 1])
    minor = float(np.corrcoef(rolled, _MINOR)[0, 1])
    mode = "major" if major > minor else "minor"
    return (tempo if tempo > 0 else None), f"{KEY_NAMES[index]} {mode}"


def mean_chroma(clip: beatgrid.Frames) -> list[float]:
    """The harmonic probe's profile: mean CQT chroma, L2-normalised."""
    mean = clip.chroma.mean(axis=1).astype(np.float64)
    norm = float(np.linalg.norm(mean))
    return (mean / norm).tolist() if norm >= 1e-10 else [0.0] * 12


def clip_features(
    audio: np.ndarray,
    sample_rate: int,
    embedders: Embedders,
    grid: beatgrid.BeatGrid | None = None,
    models=None,
) -> tuple[ClipFeatures, beatgrid.Frames | None]:
    """Features of one clip, plus its frames for pooling on other grids."""
    features = ClipFeatures(embeddings=embedders.encode(audio, sample_rate, only=models))
    clip = beatgrid.frames(audio, sample_rate)
    if clip is None:
        return features, None
    features.bpm, features.key = tempo_key(clip)
    features.chroma = mean_chroma(clip)
    if grid is not None:
        features.beat_chroma = beatgrid.pool_chroma(clip, grid)
        features.onsets = beatgrid.pool_onsets(clip, grid, ONSET_SUBDIVISIONS)
    return features, clip.without_audio()


def _unit(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    return vector / np.linalg.norm(vector)


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    return float(_unit(left) @ _unit(right))


def _chroma_as_is(left: list[float], right: list[float]) -> float:
    a, b = np.asarray(left, dtype=np.float64), np.asarray(right, dtype=np.float64)
    if np.linalg.norm(a) < 1e-10 or np.linalg.norm(b) < 1e-10:
        return 0.0
    return float((_unit(a) @ _unit(b) + 1.0) / 2.0)


def _onset_pattern(context: np.ndarray, candidate: np.ndarray) -> float:
    """Correlation of the two onset patterns on the shared grid, mapped to [0, 1]."""
    slots = min(context.shape[0], candidate.shape[0])
    context, candidate = context[:slots], candidate[:slots]
    if slots < 2 or context.std() < 1e-9 or candidate.std() < 1e-9:
        return 0.0
    return float((np.corrcoef(context, candidate)[0, 1] + 1.0) / 2.0)


def beat_scores(context_mix: ClipFeatures, candidate: ClipFeatures) -> dict[str, float]:
    if context_mix.beat_chroma is None or candidate.beat_chroma is None:
        return dict.fromkeys(
            ("chroma_beat_aligned", "progression_search", "rhythm_on_grid", "onset_pattern"), 0.0
        )
    return {
        "chroma_beat_aligned": progression.aligned_fit(
            context_mix.beat_chroma, candidate.beat_chroma
        ),
        "progression_search": progression.best_alignment(
            context_mix.beat_chroma, candidate.beat_chroma
        )[0],
        "rhythm_on_grid": progression.on_grid_ratio(candidate.onsets, ONSET_SUBDIVISIONS),
        "onset_pattern": _onset_pattern(context_mix.onsets, candidate.onsets),
    }


def load_fusion_weights() -> np.ndarray:
    data = json.loads((ROOT / "artifacts" / "fusion-deploy" / "weights.json").read_text())
    return np.asarray(data["weights"], dtype=np.float64)


def score_all(
    context_mix: ClipFeatures,
    regions: list[ClipFeatures],
    candidate: ClipFeatures,
    fusion_weights: np.ndarray,
    embedders: Embedders | None = None,
) -> dict[str, float]:
    """Every scorer's value for one candidate against one context.

    Scorers whose model was not run for these clips are left out.
    """
    scores: dict[str, float] = {}
    product = PRODUCT_MODEL
    has_product = product in candidate.embeddings and product in context_mix.embeddings
    cos_mean = cos_max = 0.0
    if has_product:
        region_matrix = np.stack([_unit(r.embeddings[product]) for r in regions])
        mean_region = _unit(region_matrix.mean(axis=0))
        vector = _unit(candidate.embeddings[product])
        cos_mean = float(mean_region @ vector)
        cos_max = float((region_matrix @ vector).max())
        scores["clap_cos_mix"] = _cosine(context_mix.embeddings[product], vector)
        scores["clap_cos_mean"] = cos_mean
        scores["clap_cos_max"] = cos_max

    tempo = tempo_match(context_mix.bpm, candidate.bpm)
    key_exact = key_match(context_mix.key, candidate.key)
    scores["tempo"] = tempo
    scores["key_exact"] = key_exact
    scores["key_fifth"] = key_match(context_mix.key, candidate.key, mode="fifth")
    scores["harmonic_transpose_invariant"] = transpose_invariant_score(
        context_mix.chroma, candidate.chroma
    )[0]
    scores["chroma_as_is"] = _chroma_as_is(context_mix.chroma, candidate.chroma)

    if has_product:
        # The linear score before the sigmoid: same ranking as the served
        # score, without the saturation that hides differences near 1.
        # Stems carry no tags, so the tag term is zero, as it is for an
        # untagged fragment online.
        base = np.array([cos_mean, cos_max, tempo, 0.0, 0.0])
        scores["fusion5_online"] = float(fusion_weights @ base)
        base[3] = key_exact
        scores["fusion5_with_key"] = float(fusion_weights @ base)

    if "laion" in candidate.embeddings and "laion" in context_mix.embeddings:
        scores["laion_cos_mix"] = _cosine(
            context_mix.embeddings["laion"], candidate.embeddings["laion"]
        )
    if (
        embedders is not None
        and "cocola" in candidate.embeddings
        and "cocola" in context_mix.embeddings
    ):
        scores["cocola"] = embedders.cocola_score(
            context_mix.embeddings["cocola"], candidate.embeddings["cocola"]
        )

    scores.update(beat_scores(context_mix, candidate))
    return scores
