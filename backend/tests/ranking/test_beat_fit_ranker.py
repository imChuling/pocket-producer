"""beat-fit-v1, the beat signals in the fusion log, and the stored records."""

import numpy as np
import pytest
from bson import ObjectId

from ranking import beat_sync
from ranking.audio_cosine import InsufficientContextError
from ranking.beat_fit_ranker import BeatFitRanker
from ranking.enrichment import attach_audio_embeddings
from ranking.fusion_ranker import FusionRanker
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint

SR = 22050
BPM = 120.0


def _clip(offset_seconds: float = 0.0, root: float = 261.63, seconds: float = 10.0):
    """Beat clicks and a sustained triad; `offset_seconds` shifts the clicks."""
    period = 60.0 / BPM
    t = np.arange(int(seconds * SR)) / SR
    y = sum(0.08 * np.sin(2 * np.pi * root * r * t) for r in (1.0, 1.26, 1.5))
    rng = np.random.default_rng(int(root))
    k = 0
    while (start := offset_seconds + k * period) < seconds - 0.05:
        a = int(start * SR)
        y[a : a + 400] += 0.6 * rng.standard_normal(400) * np.exp(-np.arange(400) / 80)
        k += 1
    return beat_sync.frames(y.astype(np.float32), SR)


@pytest.fixture(scope="module")
def session_beats():
    return beat_sync.session_beats([beat_sync.Placement(_clip(), 0.0)], BPM)


@pytest.fixture(scope="module")
def records():
    return {
        "in_step": beat_sync.encode_frames(_clip()),
        "off_beat": beat_sync.encode_frames(_clip(offset_seconds=0.19, root=277.18)),
        "silent": beat_sync.encode_frames(None),
    }


def _candidate(fid, **extra):
    return FragmentCandidate(
        fragment_id=fid, duration_seconds=10.0, created_at_iso="2026-11-01T00:00:00Z",
        audio_url="", **extra,
    )


def _request(candidates, beats=None, **session):
    return RankRequest(
        session=SessionFingerprint(
            project_id="p", playhead_seconds=0, track_count=1,
            session_beats=beats, **session,
        ),
        candidates=candidates, model_id="beat-fit-v1", limit=10,
    )


def test_in_step_candidate_ranks_first_with_beat_evidence(session_beats, records):
    response = BeatFitRanker().rank(_request(
        [_candidate("off", beat_frames=records["off_beat"]),
         _candidate("in", beat_frames=records["in_step"])],
        session_beats,
    ))
    assert [c.fragment_id for c in response.candidates] == ["in", "off"]
    top = response.candidates[0]
    assert {e.code for e in top.evidence} <= {"beat_harmony", "beat_rhythm"}
    assert top.evidence and all(e.contribution > 0 for e in top.evidence)
    assert response.signal_names == ["chroma_beat_aligned", "onset_pattern_shared_beats"]
    assert len(top.signals) == 2


def test_unopposed_rhythm_is_reported_without_changing_the_order():
    times = np.arange(431) * beat_sync.HOP_LENGTH / SR
    sounding = times < 2
    slots = (np.floor(times / (0.5 / 8)) % 8).astype(int)
    chroma = np.zeros((12, len(times)), dtype=np.float32)
    chroma[0, sounding] = 1

    def clip(accents):
        onsets = np.where(sounding, np.asarray(accents)[slots], 0).astype(np.float32)
        return beat_sync.Frames(chroma, onsets, sounding.astype(np.float32), times, 10.0)

    beats = beat_sync.session_beats([beat_sync.Placement(clip(range(1, 9)), 0)], BPM)
    response = BeatFitRanker().rank(_request([
        _candidate("flat", beat_frames=beat_sync.encode_frames(clip([1] * 8))),
        _candidate("opposed", beat_frames=beat_sync.encode_frames(clip([7, 8, 5, 6, 3, 4, 1, 2]))),
    ], beats))
    rhythm = next(e for c in response.candidates for e in c.evidence if e.code == "beat_rhythm")
    assert rhythm.raw_value < -0.9
    assert rhythm.contribution == 0
    assert response.candidates[0].score == response.candidates[1].score


def test_candidates_without_beat_data_are_skipped(session_beats, records):
    response = BeatFitRanker().rank(_request(
        [_candidate("in", beat_frames=records["in_step"]),
         _candidate("none"),
         _candidate("silent", beat_frames=records["silent"])],
        session_beats,
    ))
    assert [c.fragment_id for c in response.candidates] == ["in"]
    # A lone candidate is scored on its own values, so it still has evidence.
    assert response.candidates[0].evidence


def test_no_scorable_candidate_raises(session_beats, records):
    with pytest.raises(InsufficientContextError):
        BeatFitRanker().rank(_request([_candidate("none")], session_beats))


def test_no_tempo_raises(records):
    with pytest.raises(InsufficientContextError):
        BeatFitRanker().rank(_request([_candidate("in", beat_frames=records["in_step"])]))


def test_fusion_logs_beat_signals_without_changing_its_scores(session_beats, records):
    weights = {"weights": [6.8, 8.3, 2.0, 0.4, 1.5]}
    region = [1.0] + [0.0] * 7
    cands = [
        _candidate("a", audio_embedding=region, beat_frames=records["in_step"]),
        _candidate("b", audio_embedding=[0.6, 0.8] + [0.0] * 6, beat_frames=records["off_beat"]),
    ]
    with_beats = FusionRanker(weights).rank(_request(
        cands, session_beats, region_audio_embeddings=[region]
    ).model_copy(update={"model_id": "fusion-5sig-v1"}))
    without = FusionRanker(weights).rank(_request(
        [c.model_copy(update={"beat_frames": None}) for c in cands],
        None, region_audio_embeddings=[region],
    ))
    assert [c.score for c in with_beats.candidates] == [c.score for c in without.candidates]
    assert all(len(c.signals) == 7 for c in with_beats.candidates)
    assert with_beats.candidates[0].signals[5] > 0.9
    assert all(c.signals[5:] == [0.0, 0.0] for c in without.candidates)
    assert with_beats.signal_names[-2:] == ["chroma_beat_aligned", "onset_pattern"]


class _StubFragments:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection=None):
        wanted = set(query["_id"]["$in"])
        return [d for d in self.docs if d["_id"] in wanted and d["user_id"] == query["user_id"]]


def test_enrichment_attaches_stored_beat_frames(records):
    oid = ObjectId()
    db = {"fragments": _StubFragments([{
        "_id": oid, "user_id": "u",
        "representations": {"beat_frames": records["in_step"]},
    }])}
    request = _request([_candidate(str(oid))])
    attach_audio_embeddings(db, "u", request)
    assert request.candidates[0].beat_frames["revision"] == beat_sync.BEAT_FRAMES_REVISION


def test_ingest_adds_missing_beat_frames_without_rerunning_clap(monkeypatch, tmp_path):
    import soundfile

    from ranking import ingest
    from ranking.adapters.base import audio_sha256

    wav = tmp_path / "clip.wav"
    t = np.arange(int(3 * 44100)) / 44100
    soundfile.write(wav, (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), 44100)

    class _Blob:
        def download_to_filename(self, name):
            pathlib_copy(wav, name)

    def pathlib_copy(src, dst):
        import shutil

        shutil.copyfile(src, dst)

    class _Gcs:
        def bucket(self, _):
            return self

        def blob(self, _):
            return _Blob()

    import librosa

    waveform, _ = librosa.load(str(wav), sr=44100, mono=True)
    digest = audio_sha256(waveform.astype(np.float32), 44100)

    from types import SimpleNamespace

    adapter = SimpleNamespace(model_card=SimpleNamespace(revision="rev-1"))

    writes = []

    class _Fragments:
        def find_one(self, query, projection):
            return {"representations": {
                "audio_semantic": {"input_sha256": digest, "revision": "rev-1"},
                "chroma": {"revision": ingest.CHROMA_REVISION},
            }}

        def update_one(self, query, update):
            writes.append(update["$set"])

    monkeypatch.setattr("api._clients.get_gcs_client", lambda: _Gcs())
    monkeypatch.setattr(ingest, "_get_adapter", lambda: adapter)
    outcome = ingest._encode_sync(
        {"fragments": _Fragments()}, "u", str(ObjectId()), "gs://bucket/clip.wav"
    )
    assert outcome == "encoded"
    assert list(writes[0]) == ["representations.beat_frames"]
    assert writes[0]["representations.beat_frames"]["revision"] == beat_sync.BEAT_FRAMES_REVISION


def test_identical_candidates_keep_raw_measurements_when_relative_scores_tie(
    session_beats, records,
):
    response = BeatFitRanker().rank(_request(
        [_candidate("a", beat_frames=records["in_step"]),
         _candidate("b", beat_frames=records["in_step"])], session_beats,
    ))
    for candidate in response.candidates:
        assert candidate.score == 0
        assert len(candidate.evidence) == 2
        assert all(e.raw_value is not None for e in candidate.evidence)
        assert all(e.contribution == 0 for e in candidate.evidence)
        assert any("tied" in e.label.lower() for e in candidate.evidence)
        assert candidate.signal_available == [True, True]


def test_non_overlapping_audio_is_not_rhythm_alignment():
    times = np.arange(431) * beat_sync.HOP_LENGTH / SR
    early = times < 4.5
    late = times >= 5.0

    def clip(active):
        return beat_sync.Frames(
            np.ones((12, len(times)), dtype=np.float32),
            np.where(active, np.arange(len(times)) % 7, 0).astype(np.float32),
            active.astype(np.float32), times, 10.0,
        )

    beats = beat_sync.session_beats([beat_sync.Placement(clip(late), 0)], BPM)
    record = beat_sync.encode_frames(clip(early))
    assert beat_sync.decode_frames(record) is not None
    measured = beat_sync.candidate_measurements(beats, record)
    assert measured.shared_beats == 0
    assert measured.available == (False, False)
    with pytest.raises(InsufficientContextError):
        BeatFitRanker().rank(_request([_candidate("early", beat_frames=record)], beats))


@pytest.mark.parametrize("flat", [False, True])
def test_beat_fit_compares_onsets_only_during_four_shared_sounding_beats(flat):
    # Four sounding beats followed by sixteen beats of silence at 120 BPM.
    times = np.arange(431) * beat_sync.HOP_LENGTH / SR
    active = times < 2.0
    subdivision = np.floor(times * BPM / 60 * beat_sync.ONSET_SUBDIVISIONS) % 8
    candidate = beat_sync.Frames(
        np.ones((12, len(times)), dtype=np.float32),
        np.where(active, 1 if flat else subdivision, 0).astype(np.float32),
        active.astype(np.float32), times, 10.0,
    )
    session = beat_sync.Frames(
        candidate.chroma, np.where(active, 7 - subdivision, 0).astype(np.float32),
        candidate.rms, times, 10.0,
    )
    beats = beat_sync.session_beats([beat_sync.Placement(session, 0)], BPM)
    record = beat_sync.encode_frames(candidate)
    response = BeatFitRanker().rank(_request([_candidate("phrase", beat_frames=record)], beats))
    ranked = response.candidates[0]
    rhythm = [e for e in ranked.evidence if e.code == "beat_rhythm"]
    if flat:
        assert ranked.signal_available == [True, False]
        assert rhythm == []
    else:
        assert ranked.signal_available == [True, True]
        assert rhythm[0].raw_value == pytest.approx(-1)
        assert "4 shared beats" in rhythm[0].label
        # Fusion's historical whole-grid measurement is positive from shared silence.
        legacy = beat_sync.candidate_measurements(beats, record)
        assert legacy.onset_correlation > 0


def test_negative_correlation_is_a_signed_measurement_not_a_match(session_beats, records):
    clip = beat_sync.decode_frames(records["in_step"])
    assert clip is not None
    pattern = beat_sync.pool_onsets(clip, np.asarray(session_beats["beat_times"]))
    beats = {**session_beats, "onsets": (1 - pattern).tolist()}
    response = BeatFitRanker().rank(_request(
        [_candidate("opposite", beat_frames=records["in_step"])], beats,
    ))
    rhythm = next(e for e in response.candidates[0].evidence if e.code == "beat_rhythm")
    assert rhythm.raw_value == pytest.approx(-1)
    assert "-1.00" in rhythm.label
    assert "line up" not in rhythm.label and "falls where" not in rhythm.label
    assert response.candidates[0].signal_available == [True, True]


def test_corrupt_candidate_does_not_discard_a_valid_recommendation(session_beats, records):
    broken = {**records["in_step"], "chroma": "not base64!"}
    response = BeatFitRanker().rank(_request(
        [_candidate("good", beat_frames=records["in_step"]),
         _candidate("bad", beat_frames=broken)], session_beats,
    ))
    assert [c.fragment_id for c in response.candidates] == ["good"]


def test_corrupt_logged_beat_frames_do_not_break_five_signal_fusion(session_beats, records):
    artifact = {"weights": [1, 1, 1, 1, 1]}
    request = _request(
        [_candidate("good", beat_frames=records["in_step"], audio_embedding=[1, 0]),
         _candidate("bad", beat_frames={**records["in_step"], "onset": "!"},
                    audio_embedding=[0, 1])],
        session_beats, region_audio_embeddings=[[1, 0]],
    )
    response = FusionRanker(artifact).rank(request)
    assert len(response.candidates) == 2
    assert response.candidates[0].signal_available[-2:] == [True, True]
    assert response.candidates[1].signal_available[-2:] == [False, False]
