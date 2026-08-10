"""Tests for the online capacity-ladder adapter.

The critical property: the adapter never returns an empty success. When it
cannot score anything it raises InsufficientContextError so the service
falls back to rules-v1, which can still rank by structured features.
"""

import json
import math
from dataclasses import asdict

import pytest
from safetensors.torch import save_file

from ranking.audio_cosine import InsufficientContextError
from ranking.baselines import RulesRanker
from ranking.context_model import LadderConfig, PocketRankContext
from ranking.deepsets_ranker import DeepSetsRanker
from ranking.ladder_adapter import LadderRankerAdapter
from ranking.linear_ranker import LinearRanker
from ranking.registry import RankerRegistry
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint
from ranking.service import RankingService

DIM = 8

CONFIG = LadderConfig(
    input_dim=DIM,
    d_model=8,
    structured_dim=0,
    max_tokens=4,
    nhead=2,
    dim_feedforward=16,
    num_layers=1,
    low_rank=4,
)

MODEL_CLASSES = {
    "linear-v1": LinearRanker,
    "deepsets-v1": DeepSetsRanker,
    "pocketrank-context-v1": PocketRankContext,
}


def write_checkpoint(tmp_path, model_id: str):
    directory = tmp_path / model_id
    directory.mkdir(parents=True, exist_ok=True)
    model = MODEL_CLASSES[model_id](CONFIG)
    save_file(model.state_dict(), str(directory / "model.safetensors"))
    (directory / "config.json").write_text(json.dumps(asdict(CONFIG)))
    return directory


def candidate(fragment_id: str, embedding: list[float] | None) -> FragmentCandidate:
    return FragmentCandidate(
        fragment_id=fragment_id,
        duration_seconds=4.0,
        created_at_iso="2026-07-01T00:00:00Z",
        audio_url=f"/api/fragments/{fragment_id}/audio",
        audio_embedding=embedding,
    )


def request(
    candidates: list[FragmentCandidate],
    regions: list[list[float]] | None = None,
) -> RankRequest:
    return RankRequest(
        session=SessionFingerprint(
            project_id="p1",
            playhead_seconds=0,
            track_count=1,
            active_track_types=["audio"],
            region_audio_embeddings=regions,
        ),
        candidates=candidates,
        limit=3,
    )


REGIONS = [[0.1] * DIM, [0.2] * DIM]


@pytest.fixture(params=sorted(MODEL_CLASSES))
def ladder(request, tmp_path):
    model_id = request.param
    return LadderRankerAdapter(model_id, write_checkpoint(tmp_path, model_id))


class TestRanking:
    def test_scores_and_orders_candidates(self, ladder):
        response = ladder.rank(
            request(
                [candidate("f1", [0.3] * DIM), candidate("f2", [0.9] * DIM)],
                regions=REGIONS,
            )
        )
        assert response.model_id == ladder.model_id
        assert response.fallback_used is False
        assert len(response.candidates) == 2
        scores = [c.score for c in response.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_missing_regions_raises(self, ladder):
        with pytest.raises(InsufficientContextError):
            ladder.rank(request([candidate("f1", [0.3] * DIM)], regions=None))

    def test_non_finite_regions_raise(self, ladder):
        bad = [[math.nan] * DIM]
        with pytest.raises(InsufficientContextError):
            ladder.rank(request([candidate("f1", [0.3] * DIM)], regions=bad))

    def test_wrong_dimension_regions_raise(self, ladder):
        with pytest.raises(InsufficientContextError):
            ladder.rank(request([candidate("f1", [0.3] * DIM)], regions=[[0.1] * 3]))

    def test_all_candidates_unscorable_raises_not_empty_success(self, ladder):
        # The original bug: this returned fallback_used=false, candidates=[].
        with pytest.raises(InsufficientContextError):
            ladder.rank(request([candidate("f1", None)], regions=REGIONS))

    def test_wrong_dim_and_non_finite_candidates_are_skipped(self, ladder):
        response = ladder.rank(
            request(
                [
                    candidate("short", [0.5] * 3),
                    candidate("nan", [math.nan] * DIM),
                    candidate("ok", [0.4] * DIM),
                ],
                regions=REGIONS,
            )
        )
        assert [c.fragment_id for c in response.candidates] == ["ok"]

    def test_only_unusable_candidates_raise(self, ladder):
        with pytest.raises(InsufficientContextError):
            ladder.rank(
                request(
                    [candidate("short", [0.5] * 3), candidate("inf", [math.inf] * DIM)],
                    regions=REGIONS,
                )
            )


class TestServiceFallback:
    def test_unscorable_request_falls_back_to_rules(self, tmp_path):
        registry = RankerRegistry()
        registry.register(RulesRanker())
        registry.register(
            LadderRankerAdapter(
                "pocketrank-context-v1",
                write_checkpoint(tmp_path, "pocketrank-context-v1"),
            )
        )
        service = RankingService(registry)
        rank_request = request([candidate("f1", None)], regions=REGIONS)
        rank_request = rank_request.model_copy(
            update={"model_id": "pocketrank-context-v1"}
        )
        response = service.rank(rank_request)
        assert response.model_id == "rules-v1"
        assert response.fallback_used is True
        assert [c.fragment_id for c in response.candidates] == ["f1"]


class TestModelCard:
    def test_card_has_provenance_and_no_filesystem_path(self, tmp_path):
        directory = write_checkpoint(tmp_path, "linear-v1")
        adapter = LadderRankerAdapter("linear-v1", directory)
        card = adapter.model_card
        assert card["id"] == "linear-v1"
        assert card["trainable_parameters"] == 2
        assert card["checkpoint_hash"].startswith("sha256:")
        assert str(tmp_path) not in json.dumps(card)
