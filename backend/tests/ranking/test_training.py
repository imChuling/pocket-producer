"""Training smoke: the ladder learns a learnable weak-pair task."""

import numpy as np
import torch

from ranking.context_model import LadderConfig, PocketRankContext
from ranking.linear_ranker import LinearRanker
from ranking.training import pairwise_eval, train_model
from ranking.weak_pairs import build_weak_pairs, split_sources

DIMS = 8
CFG = LadderConfig(input_dim=DIMS, d_model=16, structured_dim=0, low_rank=4)


def learnable_items(n_sources=10, items_per_source=4, seed=0):
    rng = np.random.default_rng(seed)
    items = []
    for source_index in range(n_sources):
        direction = rng.normal(size=DIMS)
        direction /= np.linalg.norm(direction)
        for item_index in range(items_per_source):
            vector = direction + 0.25 * rng.normal(size=DIMS)
            vector /= np.linalg.norm(vector)
            items.append(
                {
                    "item_id": f"s{source_index}_i{item_index}",
                    "source_id": f"s{source_index}",
                    "embedding": list(vector),
                    "bpm": None,
                    "key": None,
                    "tags": [],
                    "duration_seconds": 4.0,
                }
            )
    return items


def split_examples():
    examples = build_weak_pairs(learnable_items(), seed=3)
    train_sources, val_sources = split_sources(
        [example["source_id"] for example in examples], seed=3, val_fraction=0.3
    )
    train = [e for e in examples if e["source_id"] in set(train_sources)]
    val = [e for e in examples if e["source_id"] in set(val_sources)]
    assert train and val
    return train, val


class TestTraining:
    def test_linear_model_learns_above_chance(self):
        train, val = split_examples()
        torch.manual_seed(0)
        model = LinearRanker(CFG)
        before = pairwise_eval(model, val, CFG)
        outcome = train_model(model, train, val, CFG, seed=0, epochs=8)
        assert outcome.val_pairwise_accuracy is not None
        assert outcome.val_pairwise_accuracy > 0.6
        assert outcome.val_pairwise_accuracy >= before - 0.05

    def test_context_model_trains_with_finite_loss(self):
        train, val = split_examples()
        torch.manual_seed(0)
        model = PocketRankContext(CFG)
        outcome = train_model(model, train, val, CFG, seed=0, epochs=2)
        assert np.isfinite(outcome.final_train_loss)
        assert outcome.val_pairwise_accuracy is not None

    def test_training_is_deterministic_given_seed(self):
        train, val = split_examples()
        results = []
        for _ in range(2):
            torch.manual_seed(0)
            model = LinearRanker(CFG)
            outcome = train_model(model, train, val, CFG, seed=0, epochs=3)
            results.append(outcome.val_pairwise_accuracy)
        assert results[0] == results[1]
