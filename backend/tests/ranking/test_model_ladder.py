"""Capacity ladder: L0 linear, L1 DeepSets, L2 PocketRank-Context.

Shared invariants: region tokens are a set (order must not matter), padding
must not change outputs, all outputs finite on CPU, and L2 stays under the
500K trainable-parameter budget.
"""

import numpy as np
import pytest
import torch

from ranking.context_model import (
    LadderConfig,
    PocketRankContext,
    load_checkpoint,
    save_checkpoint,
)
from ranking.deepsets_ranker import DeepSetsRanker
from ranking.linear_ranker import LinearRanker

CFG = LadderConfig(input_dim=64, d_model=32, structured_dim=6, max_tokens=8)


def batch(seed: int = 0, batch_size: int = 2, tokens: int = 5):
    rng = np.random.default_rng(seed)
    region_tokens = torch.tensor(
        rng.normal(size=(batch_size, tokens, CFG.input_dim)), dtype=torch.float32
    )
    mask = torch.zeros(batch_size, tokens, dtype=torch.bool)  # False = real
    candidate = torch.tensor(
        rng.normal(size=(batch_size, CFG.input_dim)), dtype=torch.float32
    )
    structured = torch.tensor(
        rng.normal(size=(batch_size, CFG.structured_dim)), dtype=torch.float32
    )
    return region_tokens, mask, candidate, structured


@pytest.fixture(params=["linear", "deepsets", "context"])
def model(request):
    torch.manual_seed(7)
    if request.param == "linear":
        return LinearRanker(CFG)
    if request.param == "deepsets":
        return DeepSetsRanker(CFG)
    return PocketRankContext(CFG)


class TestSharedInvariants:
    def test_forward_is_finite_on_cpu(self, model):
        scores = model(*batch())
        assert scores.shape == (2,)
        assert torch.isfinite(scores).all()

    def test_region_token_order_does_not_matter(self, model):
        region_tokens, mask, candidate, structured = batch()
        permutation = torch.randperm(region_tokens.shape[1])
        permuted = region_tokens[:, permutation, :]
        with torch.no_grad():
            original = model(region_tokens, mask, candidate, structured)
            shuffled = model(permuted, mask, candidate, structured)
        torch.testing.assert_close(original, shuffled, atol=1e-5, rtol=1e-4)

    def test_padding_does_not_change_output(self, model):
        region_tokens, mask, candidate, structured = batch()
        pad = torch.zeros(2, 3, CFG.input_dim)
        padded_tokens = torch.cat([region_tokens, pad], dim=1)
        padded_mask = torch.cat(
            [mask, torch.ones(2, 3, dtype=torch.bool)], dim=1
        )
        with torch.no_grad():
            original = model(region_tokens, mask, candidate, structured)
            padded = model(padded_tokens, padded_mask, candidate, structured)
        torch.testing.assert_close(original, padded, atol=1e-5, rtol=1e-4)

    def test_candidate_content_changes_output(self, model):
        region_tokens, mask, candidate, structured = batch()
        with torch.no_grad():
            base = model(region_tokens, mask, candidate, structured)
            other = model(region_tokens, mask, candidate + 1.0, structured)
        assert not torch.allclose(base, other)


class TestCapacityBudget:
    def test_context_model_stays_under_500k_at_full_size(self):
        full = PocketRankContext(
            LadderConfig(input_dim=1024, d_model=128, structured_dim=18)
        )
        trainable = sum(
            p.numel() for p in full.parameters() if p.requires_grad
        )
        assert trainable < 500_000, f"L2 has {trainable} params"

    def test_ladder_capacity_is_strictly_increasing(self):
        def count(m):
            return sum(p.numel() for p in m.parameters() if p.requires_grad)

        assert (
            count(LinearRanker(CFG))
            < count(DeepSetsRanker(CFG))
            < count(PocketRankContext(CFG))
        )


class TestCheckpointRoundtrip:
    def test_save_and_load_reproduces_outputs(self, tmp_path):
        torch.manual_seed(3)
        model = PocketRankContext(CFG)
        inputs = batch(seed=5)
        with torch.no_grad():
            expected = model(*inputs)
        path = tmp_path / "ckpt"
        save_checkpoint(model, CFG, path)
        restored, config = load_checkpoint(path)
        assert config == CFG
        with torch.no_grad():
            actual = restored(*inputs)
        torch.testing.assert_close(expected, actual)

    def test_checkpoint_records_parameter_count(self, tmp_path):
        model = PocketRankContext(CFG)
        path = tmp_path / "ckpt"
        save_checkpoint(model, CFG, path)
        import json

        card = json.loads((path / "model_card.json").read_text())
        assert card["trainable_parameters"] == sum(
            p.numel() for p in model.parameters() if p.requires_grad
        )
        assert card["parameter_budget"] == 500_000
