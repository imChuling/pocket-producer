"""Zero-shot instrument-role classification over CLAP embeddings.

Uses the same vocabulary and prompt template as the backbone bake-off P2
probe. Classification is deterministic given fixed prompt embeddings —
no model inference at query time, only pre-computed vector dot products.

The probe runs entirely on pre-stored CLAP audio embeddings; it never
touches raw audio at serving time.
"""

import numpy as np

ROLE_VOCAB: tuple[str, ...] = (
    "percussion", "bass", "chords", "melody", "fx", "vocal",
)

ROLE_PROMPT_TEMPLATE = "a {role} loop"

# 6-class softmax over CLAP cosines yields max ~0.22; the old 0.25
# threshold was unreachable, silently disabling the probe.
CONFIDENCE_THRESHOLD = 0.18


def _softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - x.max()
    exp = np.exp(shifted)
    return exp / exp.sum()


class RoleProbe:
    """Classify CLAP audio embeddings into instrument roles."""

    def __init__(self, prompt_embeddings: np.ndarray):
        normed = np.asarray(prompt_embeddings, dtype=np.float64)
        norms = np.linalg.norm(normed, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        self._prompts = normed / norms

    def classify(self, embedding: list[float] | np.ndarray) -> tuple[str, float]:
        audio = np.asarray(embedding, dtype=np.float64).ravel()
        norm = np.linalg.norm(audio)
        if norm == 0:
            return ROLE_VOCAB[0], 0.0
        audio = audio / norm
        cosines = self._prompts @ audio
        probs = _softmax(cosines)
        best = int(np.argmax(probs))
        return ROLE_VOCAB[best], float(probs[best])

    def session_roles(
        self,
        region_embeddings: list[list[float]],
        threshold: float = CONFIDENCE_THRESHOLD,
    ) -> dict[str, float]:
        """Classify each session region and return present roles with max confidence."""
        present: dict[str, float] = {}
        for emb in region_embeddings:
            role, conf = self.classify(emb)
            if conf >= threshold:
                present[role] = max(present.get(role, 0.0), conf)
        return present

    def gap_score(
        self,
        candidate_embedding: list[float] | np.ndarray,
        session_roles: dict[str, float],
    ) -> tuple[str | None, float]:
        """Return (role, confidence) if the candidate fills a missing role, else (None, 0)."""
        role, conf = self.classify(candidate_embedding)
        if role not in session_roles and conf >= CONFIDENCE_THRESHOLD:
            return role, conf
        return None, 0.0


def build_probe_from_adapter(adapter) -> RoleProbe:
    """Create a RoleProbe by encoding role prompts through a CLAP adapter."""
    prompts = [ROLE_PROMPT_TEMPLATE.format(role=r) for r in ROLE_VOCAB]
    embeddings = adapter.encode_text(prompts)
    return RoleProbe(np.asarray(embeddings))
