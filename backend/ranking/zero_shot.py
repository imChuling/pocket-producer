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


def style_scores(
    adapter: AudioRepresentationAdapter,
    waveform: np.ndarray,
    sample_rate: int,
) -> dict[str, float]:
    audio = np.asarray(adapter.encode_audio(waveform, sample_rate)).reshape(-1)
    prompts = [
        STYLE_PROMPT_TEMPLATE.format(style=style) for style in STYLE_VOCABULARY
    ]
    texts = adapter.encode_text(prompts)
    if texts is None:
        raise ValueError(
            f"{adapter.model_card.model_id} has no text tower; "
            "zero-shot styles need an audio-text model"
        )
    texts = np.asarray(texts)
    audio = audio / np.linalg.norm(audio)
    texts = texts / np.linalg.norm(texts, axis=1, keepdims=True)
    cosines = texts @ audio
    return {
        style: float(score)
        for style, score in zip(STYLE_VOCABULARY, cosines, strict=True)
    }
