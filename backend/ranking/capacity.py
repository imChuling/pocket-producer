"""Measure the capacity ladder: trainable parameters and CPU latency.

Numbers reported anywhere (model card, paper) must come from this
measurement, never from hand calculations.
"""

import statistics
import time

import numpy as np
import torch

from ranking.context_model import (
    PARAMETER_BUDGET,
    LadderConfig,
    PocketRankContext,
    trainable_parameters,
)
from ranking.deepsets_ranker import DeepSetsRanker
from ranking.linear_ranker import LinearRanker


def build_ladder(config: LadderConfig) -> list[torch.nn.Module]:
    return [LinearRanker(config), DeepSetsRanker(config), PocketRankContext(config)]


def synthetic_batch(config: LadderConfig, seed: int, batch_size: int, tokens: int):
    rng = np.random.default_rng(seed)
    region_tokens = torch.tensor(
        rng.normal(size=(batch_size, tokens, config.input_dim)), dtype=torch.float32
    )
    mask = torch.zeros(batch_size, tokens, dtype=torch.bool)
    candidate = torch.tensor(
        rng.normal(size=(batch_size, config.input_dim)), dtype=torch.float32
    )
    structured = torch.tensor(
        rng.normal(size=(batch_size, config.structured_dim)), dtype=torch.float32
    )
    return region_tokens, mask, candidate, structured


def measure_ladder(
    config: LadderConfig,
    seed: int = 20260725,
    batch_size: int = 32,
    tokens: int = 32,
    repeats: int = 30,
) -> dict:
    torch.manual_seed(seed)
    inputs = synthetic_batch(config, seed, batch_size, tokens)
    results: dict[str, dict] = {}
    for model in build_ladder(config):
        with torch.no_grad():
            model(*inputs)  # warmup
            latencies_ms = []
            for _ in range(repeats):
                start = time.perf_counter()
                scores = model(*inputs)
                latencies_ms.append((time.perf_counter() - start) * 1000)
        params = trainable_parameters(model)
        results[model.model_id] = {
            "trainable_parameters": params,
            "within_budget": params < PARAMETER_BUDGET,
            "cpu_latency_ms_p50": round(statistics.median(latencies_ms), 3),
            "cpu_latency_ms_p95": round(
                sorted(latencies_ms)[max(0, int(len(latencies_ms) * 0.95) - 1)], 3
            ),
            "batch_size": batch_size,
            "tokens": tokens,
            "outputs_finite": bool(torch.isfinite(scores).all()),
        }
    return {
        "config": {
            "input_dim": config.input_dim,
            "d_model": config.d_model,
            "structured_dim": config.structured_dim,
        },
        "seed": seed,
        "parameter_budget": PARAMETER_BUDGET,
        "models": results,
    }
