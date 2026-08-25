"""Unit tests for the LLM intent layer (parse normalization + pure apply)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from ranking import intent as intent_mod
from ranking.intent import _normalize, apply_parsed_intent, parse_intent
from ranking.schemas import (
    FragmentCandidate,
    ParsedIntent,
    RankRequest,
    SessionFingerprint,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    intent_mod._cache.clear()
    yield
    intent_mod._cache.clear()


def _fake_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.models.generate_content.return_value = MagicMock(
        text=json.dumps(payload)
    )
    return client


class TestNormalize:
    def test_lowercases_dedupes_and_caps_tags(self):
        parsed = _normalize({"tags": ["Dark", "dark", "Cinematic"] + [f"t{i}" for i in range(10)], "roles": []})
        assert parsed.tags[:2] == ["dark", "cinematic"]
        assert len(parsed.tags) == intent_mod.MAX_TAGS

    def test_roles_restricted_to_vocabulary(self):
        parsed = _normalize({"tags": ["dark"], "roles": ["Bass", "kazoo", "drums"]})
        assert parsed.roles == ["bass", "drums"]

    def test_bpm_out_of_range_dropped(self):
        assert _normalize({"tags": ["x"], "roles": [], "bpm": 500}).bpm is None
        assert _normalize({"tags": ["x"], "roles": [], "bpm": 90}).bpm == 90

    def test_unparseable_key_dropped(self):
        assert _normalize({"tags": ["x"], "roles": [], "key": "H sharp blues"}).key is None
        assert _normalize({"tags": ["x"], "roles": [], "key": "A Min"}).key == "a minor"

    def test_empty_result_is_none(self):
        assert _normalize({"tags": [], "roles": []}) is None


class TestParseIntent:
    def test_parses_structured_response(self):
        client = _fake_client(
            {"tags": ["dark", "cinematic"], "roles": ["bass"], "bpm": 90, "key": "a minor"}
        )
        with patch.object(intent_mod, "_get_genai_client", return_value=client):
            parsed = parse_intent("darker, more cinematic, but not too heavy")
        assert parsed == ParsedIntent(
            tags=["dark", "cinematic"], roles=["bass"], bpm=90, key="a minor"
        )

    def test_empty_text_returns_none_without_call(self):
        client = _fake_client({})
        with patch.object(intent_mod, "_get_genai_client", return_value=client):
            assert parse_intent("   ") is None
        client.models.generate_content.assert_not_called()

    def test_failure_returns_none(self):
        client = MagicMock()
        client.models.generate_content.side_effect = RuntimeError("api down")
        with patch.object(intent_mod, "_get_genai_client", return_value=client):
            assert parse_intent("dark bass") is None

    def test_cache_hits_skip_second_call(self):
        client = _fake_client({"tags": ["dark"], "roles": []})
        with patch.object(intent_mod, "_get_genai_client", return_value=client):
            first = parse_intent("Dark  Bass")
            second = parse_intent("dark bass")
        assert first == second
        assert client.models.generate_content.call_count == 1


def _request(session: SessionFingerprint) -> RankRequest:
    return RankRequest(
        session=session,
        candidates=[
            FragmentCandidate(
                fragment_id="f1",
                duration_seconds=8,
                created_at_iso="2026-07-01T00:00:00Z",
                audio_url="/api/fragments/f1/audio",
            )
        ],
    )


class TestApplyParsedIntent:
    def test_no_parsed_intent_is_identity(self):
        request = _request(SessionFingerprint(project_id="p", playhead_seconds=0, track_count=0))
        assert apply_parsed_intent(request) is request

    def test_expands_text_intent_with_new_tokens_only(self):
        session = SessionFingerprint(
            project_id="p",
            playhead_seconds=0,
            track_count=0,
            text_intent="dark bass",
            parsed_intent=ParsedIntent(tags=["dark", "cinematic"], roles=["drums"]),
        )
        enriched = apply_parsed_intent(_request(session))
        assert enriched.session.text_intent == "dark bass cinematic drums"

    def test_llm_fills_blank_bpm_and_key_only(self):
        session = SessionFingerprint(
            project_id="p",
            playhead_seconds=0,
            track_count=0,
            parsed_intent=ParsedIntent(tags=["dark"], bpm=90, key="a minor"),
        )
        enriched = apply_parsed_intent(_request(session))
        assert enriched.session.bpm == 90
        assert enriched.session.key == "a minor"

    def test_live_session_values_always_win(self):
        session = SessionFingerprint(
            project_id="p",
            playhead_seconds=0,
            track_count=0,
            bpm=120,
            key="C major",
            parsed_intent=ParsedIntent(tags=["dark"], bpm=90, key="a minor"),
        )
        enriched = apply_parsed_intent(_request(session))
        assert enriched.session.bpm == 120
        assert enriched.session.key == "C major"

    def test_original_request_not_mutated(self):
        session = SessionFingerprint(
            project_id="p",
            playhead_seconds=0,
            track_count=0,
            text_intent="dark",
            parsed_intent=ParsedIntent(tags=["cinematic"]),
        )
        request = _request(session)
        apply_parsed_intent(request)
        assert request.session.text_intent == "dark"
