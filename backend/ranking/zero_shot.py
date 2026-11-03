"""Zero-shot style evidence over a fixed, versioned vocabulary.

Style tags come from cosine similarity between the fragment's audio embedding
and text-prompt embeddings of a closed vocabulary — deterministic and fully
reproducible, unlike free-form LLM tagging. The vocabulary is part of the
experiment configuration: changing it is a versioned change.
"""

import numpy as np

from ranking.adapters.base import AudioRepresentationAdapter

STYLE_VOCABULARY: tuple[str, ...] = (
    "dark",
    "bright",
    "melancholic",
    "uplifting",
    "aggressive",
    "calm",
    "lo-fi",
    "cinematic",
    "ambient",
    "techno",
    "house",
    "hip hop",
    "rock",
    "jazz",
    "acoustic",
    "electronic",
)

STYLE_PROMPT_TEMPLATE = "a {style} music recording"

# Prompt embeddings depend only on the (frozen) text tower, so they are
# encoded once per adapter instead of on every ingest.
_prompt_cache: dict[int, np.ndarray] = {}


def _prompt_embeddings(adapter: AudioRepresentationAdapter) -> np.ndarray:
    key = id(adapter)
    cached = _prompt_cache.get(key)
    if cached is not None:
        return cached
    prompts = [STYLE_PROMPT_TEMPLATE.format(style=style) for style in STYLE_VOCABULARY]
    texts = adapter.encode_text(prompts)
    if texts is None:
        raise ValueError(
            f"{adapter.model_card.model_id} has no text tower; "
            "zero-shot styles need an audio-text model"
        )
    texts = np.asarray(texts, dtype=np.float64)
    texts = texts / np.linalg.norm(texts, axis=1, keepdims=True)
    _prompt_cache[key] = texts
    return texts


def style_scores(
    adapter: AudioRepresentationAdapter,
    waveform: np.ndarray,
    sample_rate: int,
    audio_vector: np.ndarray | None = None,
) -> dict[str, float]:
    """Cosine of the fragment against the style prompts.

    Pass `audio_vector` when the caller has already encoded the audio (ingest
    does, for the stored representation) to avoid a second forward pass.
    """
    if audio_vector is None:
        audio_vector = adapter.encode_audio(waveform, sample_rate)
    audio = np.asarray(audio_vector, dtype=np.float64).reshape(-1)
    texts = _prompt_embeddings(adapter)
    audio = audio / np.linalg.norm(audio)
    cosines = texts @ audio
    return {
        style: float(score)
        for style, score in zip(STYLE_VOCABULARY, cosines, strict=True)
    }
