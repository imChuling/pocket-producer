"""Weak-pair construction: same-source positives, typed negatives, no leakage."""

import numpy as np

from ranking.weak_pairs import build_weak_pairs, split_sources


def unit(rng, dims=8):
    vector = rng.normal(size=dims)
    return list(vector / np.linalg.norm(vector))


def make_items(n_sources=6, items_per_source=4, seed=0):
    rng = np.random.default_rng(seed)
    items = []
    for source_index in range(n_sources):
        direction = np.array(unit(rng))
        for item_index in range(items_per_source):
            noise = np.array(unit(rng)) * 0.3
            vector = direction + noise
            vector = vector / np.linalg.norm(vector)
            items.append(
                {
                    "item_id": f"s{source_index}_i{item_index}",
                    "source_id": f"s{source_index}",
                    "embedding": list(vector),
                    "bpm": 90 + 10 * source_index,
                    "key": "a minor" if source_index % 2 == 0 else "c major",
                    "tags": [f"tag{source_index}"],
                    "duration_seconds": 4.0,
                }
            )
    return items


class TestBuildWeakPairs:
    def test_positive_shares_source_with_context(self):
        examples = build_weak_pairs(make_items(), seed=1)
        assert examples
        for example in examples:
            assert all(
                source == example["source_id"]
                for source in example["context_sources"]
            )
            assert example["positive_source"] == example["source_id"]

    def test_negatives_never_come_from_the_context_source(self):
        for example in build_weak_pairs(make_items(), seed=1):
            assert all(
                source != example["source_id"]
                for source in example["negative_sources"]
            )

    def test_context_size_between_two_and_four(self):
        for example in build_weak_pairs(make_items(), seed=1):
            assert 2 <= len(example["context_embeddings"]) <= 4

    def test_sources_with_fewer_than_three_items_are_skipped(self):
        items = make_items(n_sources=2, items_per_source=2)
        assert build_weak_pairs(items, seed=1) == []

    def test_deterministic_given_seed(self):
        first = build_weak_pairs(make_items(), seed=42)
        second = build_weak_pairs(make_items(), seed=42)
        assert first == second

    def test_different_seed_changes_sampling(self):
        a = build_weak_pairs(make_items(), seed=1)
        b = build_weak_pairs(make_items(), seed=2)
        assert a != b

    def test_negative_types_are_labeled(self):
        types = {
            negative_type
            for example in build_weak_pairs(make_items(), seed=1)
            for negative_type in example["negative_types"]
        }
        assert types <= {"easy", "hard_tempo_key", "hard_similar"}
        assert "easy" in types
        assert "hard_similar" in types


class TestSplitSources:
    def test_no_source_appears_in_both_splits(self):
        sources = [f"s{i}" for i in range(50)]
        train, val = split_sources(sources, seed=7, val_fraction=0.2)
        assert set(train) & set(val) == set()
        assert set(train) | set(val) == set(sources)

    def test_split_is_deterministic(self):
        sources = [f"s{i}" for i in range(30)]
        assert split_sources(sources, seed=7) == split_sources(sources, seed=7)

    def test_val_fraction_roughly_respected(self):
        sources = [f"s{i}" for i in range(200)]
        _, val = split_sources(sources, seed=7, val_fraction=0.2)
        assert 20 <= len(val) <= 60
