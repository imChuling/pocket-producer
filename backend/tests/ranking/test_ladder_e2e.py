"""End-to-end serving tests against the real trained FSLD checkpoints.

Uses the actual artifact directory committed to the repo, registered
through the same POCKET_LADDER_DIR path production uses. Skipped when the
checkpoints are absent (e.g. a shallow checkout without artifacts).
"""

import pathlib

import pytest

from ranking.offline_eval import LADDER_MODEL_IDS
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint

ARTIFACTS = (
    pathlib.Path(__file__).resolve().parents[3]
    / "artifacts"
    / "pocketrank-context-fsld-v1"
)

pytestmark = pytest.mark.skipif(
    not all(
        (ARTIFACTS / model_id / "model.safetensors").is_file()
        for model_id in LADDER_MODEL_IDS
    ),
    reason="trained FSLD checkpoints not present",
)

DIM = 1024


@pytest.fixture(scope="module")
def service():
    import os

    os.environ["POCKET_LADDER_DIR"] = str(ARTIFACTS)
    try:
        from ranking.service import default_service

        yield default_service()
    finally:
        os.environ.pop("POCKET_LADDER_DIR", None)


def request(model_id: str, with_embeddings: bool) -> RankRequest:
    embedding = [0.02] * DIM if with_embeddings else None
    return RankRequest(
        session=SessionFingerprint(
            project_id="p1",
            bpm=120,
            playhead_seconds=8,
            track_count=2,
            active_track_types=["audio"],
            region_audio_embeddings=[[0.01] * DIM, [0.03] * DIM],
        ),
        candidates=[
            FragmentCandidate(
                fragment_id=f"f{index}",
                duration_seconds=4.0,
                bpm=120,
                created_at_iso="2026-07-01T00:00:00Z",
                audio_url=f"/api/fragments/f{index}/audio",
                audio_embedding=(
                    [value * (index + 1) for value in embedding]
                    if embedding
                    else None
                ),
            )
            for index in range(3)
        ],
        model_id=model_id,
        limit=3,
    )


@pytest.mark.parametrize("model_id", LADDER_MODEL_IDS)
def test_each_ladder_model_serves_without_fallback(service, model_id):
    response = service.rank(request(model_id, with_embeddings=True))
    assert response.model_id == model_id
    assert response.fallback_used is False
    assert len(response.candidates) == 3
    scores = [candidate.score for candidate in response.candidates]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize("model_id", LADDER_MODEL_IDS)
def test_unscorable_candidates_fall_back_to_rules(service, model_id):
    response = service.rank(request(model_id, with_embeddings=False))
    assert response.model_id == "rules-v1"
    assert response.fallback_used is True
    assert len(response.candidates) == 3


def test_model_cards_expose_ladder_provenance(service):
    cards = {card["id"]: card for card in service.model_cards()}
    for model_id in LADDER_MODEL_IDS:
        assert model_id in cards
        assert cards[model_id]["checkpoint_hash"].startswith("sha256:")
        assert "artifacts" not in str(cards[model_id])
