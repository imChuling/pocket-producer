"""BPR training over weak pairs for the capacity ladder.

Deterministic given a seed. Weak labels pretrain only — reported numbers are
validation pairwise accuracy on source-held-out examples, never test claims.
"""

from dataclasses import dataclass

import numpy as np
import torch

from ranking.context_model import LadderConfig
from ranking.weak_pairs import CONTEXT_MAX


@dataclass
class TrainOutcome:
    model_id: str
    val_pairwise_accuracy: float | None
    train_examples: int
    val_examples: int
    epochs: int
    final_train_loss: float


def _example_tensors(example: dict, config: LadderConfig):
    context = torch.tensor(example["context_embeddings"], dtype=torch.float32)
    tokens = torch.zeros(CONTEXT_MAX, config.input_dim)
    mask = torch.ones(CONTEXT_MAX, dtype=torch.bool)
    tokens[: context.shape[0]] = context
    mask[: context.shape[0]] = False
    positive = torch.tensor(example["positive_embedding"], dtype=torch.float32)
    negatives = torch.tensor(example["negative_embeddings"], dtype=torch.float32)
    return tokens, mask, positive, negatives


def _score(model, tokens, mask, candidate, config: LadderConfig):
    batch = candidate.shape[0]
    structured = torch.zeros(batch, config.structured_dim)
    return model(
        tokens.unsqueeze(0).expand(batch, -1, -1),
        mask.unsqueeze(0).expand(batch, -1),
        candidate,
        structured,
    )


def pairwise_eval(model, examples: list[dict], config: LadderConfig) -> float | None:
    if not examples:
        return None
    wins = 0.0
    total = 0
    with torch.no_grad():
        for example in examples:
            tokens, mask, positive, negatives = _example_tensors(example, config)
            candidates = torch.cat([positive.unsqueeze(0), negatives], dim=0)
            scores = _score(model, tokens, mask, candidates, config)
            positive_score = scores[0]
            for negative_score in scores[1:]:
                if positive_score > negative_score:
                    wins += 1.0
                elif positive_score == negative_score:
                    wins += 0.5
                total += 1
    return round(wins / total, 4) if total else None


def train_model(
    model,
    train_examples: list[dict],
    val_examples: list[dict],
    config: LadderConfig,
    seed: int,
    epochs: int = 20,
    lr: float = 1e-3,
    weight_decay: float = 0.0,
    patience: int = 0,
) -> TrainOutcome:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    import copy

    model.train()
    final_loss = float("nan")
    best_val = -1.0
    best_state = None
    wait = 0
    actual_epochs = 0
    for _epoch in range(epochs):
        actual_epochs = _epoch + 1
        order = rng.permutation(len(train_examples))
        losses = []
        for index in order:
            example = train_examples[int(index)]
            tokens, mask, positive, negatives = _example_tensors(example, config)
            candidates = torch.cat([positive.unsqueeze(0), negatives], dim=0)
            scores = _score(model, tokens, mask, candidates, config)
            diff = scores[0] - scores[1:]
            loss = -torch.nn.functional.logsigmoid(diff).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss))
        final_loss = float(np.mean(losses)) if losses else float("nan")
        if patience > 0:
            val_acc = pairwise_eval(model, val_examples, config) or 0.0
            if val_acc > best_val:
                best_val = val_acc
                best_state = copy.deepcopy(model.state_dict())
                wait = 0
            else:
                wait += 1
                if wait >= patience:
                    break
    if patience > 0 and best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return TrainOutcome(
        model_id=model.model_id,
        val_pairwise_accuracy=pairwise_eval(model, val_examples, config),
        train_examples=len(train_examples),
        val_examples=len(val_examples),
        epochs=actual_epochs,
        final_train_loss=round(final_loss, 4),
    )
