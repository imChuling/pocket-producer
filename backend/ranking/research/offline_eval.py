"""Offline pairwise evaluation over a fixed labeled dataset.

Every example carries its own precomputed embeddings, so evaluation never
calls a network. A model that cannot honestly score an example (missing
intent embedding, missing candidate vector, no session context) SKIPS it and
the skip is reported — silent zeros would fake ties.
"""

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from ranking.audio_cosine import AudioCosineRanker, InsufficientContextError
from ranking.baselines import RulesRanker
from ranking.mean_session import MeanSessionRanker
from ranking.metrics import pairwise_accuracy
from ranking.recency import RecencyRanker
from ranking.schemas import FragmentCandidate, RankRequest, SessionFingerprint
from ranking.text_cosine import TextCosineRanker


class SkipExampleError(Exception):
    """This model cannot honestly score this example."""


def _request(example: dict) -> RankRequest:
    return RankRequest(
        session=SessionFingerprint(**example["session"]),
        candidates=[FragmentCandidate(**c) for c in example["candidates"]],
        limit=min(10, len(example["candidates"])),
    )


def _scores_from_ranker(ranker, example: dict) -> dict[str, float]:
    try:
        response = ranker.rank(_request(example))
    except InsufficientContextError as error:
        raise SkipExampleError(str(error)) from error
    return {c.fragment_id: c.score for c in response.candidates}


def _require_candidate_field(example: dict, field: str) -> None:
    for candidate in example["candidates"]:
        if not candidate.get(field):
            raise SkipExampleError(f"candidate {candidate['fragment_id']} lacks {field}")


def _score_rules(example: dict) -> dict[str, float]:
    return _scores_from_ranker(RulesRanker(), example)


def _score_recency(example: dict) -> dict[str, float]:
    return _scores_from_ranker(RecencyRanker(), example)


def _score_text_only(example: dict) -> dict[str, float]:
    intent_vector = example.get("intent_text_embedding")
    if not intent_vector:
        raise SkipExampleError("no intent_text_embedding on example")
    _require_candidate_field(example, "text_embedding")
    return _scores_from_ranker(
        TextCosineRanker(text_encoder=lambda _text: intent_vector), example
    )


def _score_audio_cosine(example: dict) -> dict[str, float]:
    intent_vector = example.get("intent_audio_embedding")
    if not intent_vector:
        raise SkipExampleError("no intent_audio_embedding on example")
    _require_candidate_field(example, "audio_embedding")
    return _scores_from_ranker(
        AudioCosineRanker(text_encoder=lambda _text: intent_vector), example
    )


def _score_mean_session(example: dict) -> dict[str, float]:
    _require_candidate_field(example, "audio_embedding")
    return _scores_from_ranker(MeanSessionRanker(), example)


SCORERS: dict[str, Callable[[dict], dict[str, float]]] = {
    "rules-v1": _score_rules,
    "recency-v1": _score_recency,
    "text-only-v1": _score_text_only,
    "audio-cosine-v1": _score_audio_cosine,
    "mean-session-v1": _score_mean_session,
}

LADDER_MODEL_IDS = ("linear-v1", "deepsets-v1", "pocketrank-context-v1")


def load_ladder_adapters(checkpoint_base: str | Path) -> dict:
    """Load whichever capacity-ladder checkpoints exist under the base dir."""
    from ranking.ladder_adapter import LadderRankerAdapter

    adapters = {}
    base = Path(checkpoint_base)
    for model_id in LADDER_MODEL_IDS:
        directory = base / model_id
        if (directory / "model.safetensors").is_file():
            adapters[model_id] = LadderRankerAdapter(model_id, directory)
    return adapters


def ladder_scorers(
    adapters: dict,
) -> dict[str, Callable[[dict], dict[str, float]]]:
    """Checkpoint-backed scorers for the learned models.

    Examples where any candidate lacks an audio embedding are skipped rather
    than partially scored: a pairwise label with one unscored side would
    silently compare a model score against the 0.0 default.
    """

    def make(adapter) -> Callable[[dict], dict[str, float]]:
        def score(example: dict) -> dict[str, float]:
            _require_candidate_field(example, "audio_embedding")
            return _scores_from_ranker(adapter, example)

        return score

    return {model_id: make(adapter) for model_id, adapter in adapters.items()}


def evaluate_examples(
    examples: list[dict],
    model_names: list[str],
    extra_scorers: dict[str, Callable[[dict], dict[str, float]]] | None = None,
) -> dict:
    scorers = {**SCORERS, **(extra_scorers or {})}
    unknown = set(model_names) - set(scorers)
    if unknown:
        raise ValueError(f"unknown models: {sorted(unknown)}")
    results: dict[str, dict] = {}
    for name in model_names:
        outcomes = []
        per_participant: dict[str, list[dict]] = defaultdict(list)
        skipped = 0
        for example in examples:
            label = example["label"]
            if label.get("type") != "pairwise":
                raise ValueError(
                    f"expected pairwise labels, got {label.get('type')!r}"
                )
            try:
                scores = scorers[name](example)
            except SkipExampleError:
                skipped += 1
                continue
            outcome = {
                "preferred_score": scores.get(label["preferred_id"], 0.0),
                "rejected_score": scores.get(label["rejected_id"], 0.0),
            }
            outcomes.append(outcome)
            per_participant[example.get("participant_hash", "unknown")].append(
                outcome
            )
        results[name] = {
            "pairwise_accuracy": (
                round(pairwise_accuracy(outcomes), 4) if outcomes else None
            ),
            "evaluated": len(outcomes),
            "skipped": skipped,
            "per_participant": {
                participant: {
                    "accuracy": round(pairwise_accuracy(participant_outcomes), 4),
                    "n": len(participant_outcomes),
                }
                for participant, participant_outcomes in sorted(
                    per_participant.items()
                )
            },
        }
    return {
        "primary_metric": "pairwise_accuracy",
        "grouping": "participant",
        "label_type": "pairwise",
        "n_examples": len(examples),
        "models": results,
    }
