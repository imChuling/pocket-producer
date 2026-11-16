"""Stable ranking protocol.

Once frontend integration starts these models may only gain
backward-compatible fields; renames and removals are breaking.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ParsedIntent(BaseModel):
    """LLM interpretation of a free-text intent.

    Produced by /api/ranking/intent, shown to the user as editable chips,
    then echoed back inside SessionFingerprint. The ranker treats it as a
    proposal: live session values (bpm, key) always win; parsed values only
    fill blanks. Tags/roles are lowercase tokens in the tagging vocabulary.
    """

    tags: list[str] = []
    roles: list[str] = []
    bpm: float | None = Field(default=None, gt=0)
    key: str | None = None


class SessionBeats(BaseModel):
    """The session's first 10 s on its own beat grid (ranking/beat_sync.py).

    Built by /api/ranking/session-embed from the project tempo and each
    region's timeline position, and echoed back by the browser.
    """

    bpm: float = Field(gt=0)
    beat_times: list[float] = Field(min_length=2, max_length=64)
    beat_chroma: list[list[float]]
    onsets: list[float]

    @model_validator(mode="after")
    def _shapes(self):
        beats = len(self.beat_times) - 1
        if len(self.beat_chroma) != beats or any(len(row) != 12 for row in self.beat_chroma):
            raise ValueError("beat_chroma must have one 12-bin row per beat")
        if beats == 0 or len(self.onsets) % beats != 0:
            raise ValueError("onsets must hold the same number of slots for every beat")
        return self


class SessionFingerprint(BaseModel):
    project_id: str
    bpm: float | None = None
    key: str | None = None
    playhead_seconds: float = Field(ge=0)
    track_count: int = Field(ge=0)
    active_track_types: list[str] = []
    recent_entity_ids: list[str] = []
    text_intent: str = ""
    # Tags of fragments recently used in this session; context for the
    # fusion ranker's tag-overlap signal. Backward-compatible addition.
    context_tags: list[str] = []
    # Audio embeddings of the session's active regions, when available.
    # Populated server-side once Nexus sample audio is accessible; absent
    # means mean-session ranking cannot run and must fall back.
    region_audio_embeddings: list[list[float]] | None = None
    region_chroma_vectors: list[list[float]] | None = None
    # LLM interpretation of text_intent (user-reviewed). Backward-compatible
    # addition; absent means intent matching falls back to raw token overlap.
    parsed_intent: ParsedIntent | None = None
    # Beat-synchronous chroma and onsets for beat-fit-v1 and logging.
    # Backward-compatible addition; absent when the tempo is unknown.
    session_beats: SessionBeats | None = None


class FragmentCandidate(BaseModel):
    fragment_id: str
    duration_seconds: float = Field(gt=0)
    bpm: float | None = None
    key: str | None = None
    tags: list[str] = []
    created_at_iso: str
    audio_url: str
    audio_embedding: list[float] | None = None
    text_embedding: list[float] | None = None
    chroma_vector: list[float] | None = None
    # Stored frame analysis of the fragment's first 10 s
    # (representations.beat_frames), attached server-side.
    beat_frames: dict | None = None


class RankRequest(BaseModel):
    session: SessionFingerprint
    candidates: list[FragmentCandidate]
    model_id: str = "rules-v1"
    limit: int = Field(default=3, ge=1, le=10)


class RankEvidence(BaseModel):
    code: Literal[
        "tempo_match", "key_match", "track_gap", "intent_match",
        "novelty", "recency", "model_signal", "role_gap_fill", "harmonic_fit",
        "timbral_match", "tag_overlap", "beat_harmony", "beat_rhythm",
    ]
    label: str
    contribution: float


class RankedCandidate(BaseModel):
    fragment_id: str
    score: float
    evidence: list[RankEvidence]
    # Signal vector phi(s, x) the score was computed from, when the ranker
    # exposes one; logged with the served list so musician decisions can
    # later supervise the fusion weights. Backward-compatible addition.
    signals: list[float] | None = None


class RankResponse(BaseModel):
    request_id: str
    model_id: str
    fallback_used: bool
    candidates: list[RankedCandidate]
    # Names of the entries in each candidate's `signals`, when present.
    signal_names: list[str] | None = None


class FeedbackEvent(BaseModel):
    request_id: str
    project_id: str
    fragment_id: str
    event: Literal["preview", "accept", "reject", "insert", "undo"]
    rank_position: int = Field(ge=1)
    model_id: str
