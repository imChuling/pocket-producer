"""PocketRank-Context: L2 of the capacity ladder.

A small attention model over session region tokens with a low-rank
candidate-context interaction and a structured-feature branch, kept under a
hard 500K trainable-parameter budget. It is a challenger, not a default: it
ships only if it beats the simpler ladder rungs on held-out data.

Region tokens are a set — no positional encodings; temporal information
lives inside the token features themselves.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn

PARAMETER_BUDGET = 500_000


@dataclass(frozen=True)
class LadderConfig:
    input_dim: int
    d_model: int = 128
    structured_dim: int = 18
    max_tokens: int = 32
    nhead: int = 4
    dim_feedforward: int = 256
    num_layers: int = 2
    dropout: float = 0.10
    low_rank: int = 16


def masked_attention_pool(
    encoded: torch.Tensor, mask: torch.Tensor, query: torch.Tensor
) -> torch.Tensor:
    """Attention-pool real tokens; padded positions (mask=True) are excluded."""
    scores = encoded @ query
    scores = scores.masked_fill(mask, float("-inf"))
    weights = torch.softmax(scores, dim=-1)
    return torch.einsum("bt,btd->bd", weights, encoded)


class PocketRankContext(nn.Module):
    model_id = "pocketrank-context-v1"

    def __init__(self, config: LadderConfig):
        super().__init__()
        self.config = config
        # A shared projection keeps region and candidate representations in
        # one metric space and keeps a 1024-d backbone under the 500K budget.
        self.input_projection = nn.Linear(config.input_dim, config.d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            batch_first=True,
            norm_first=True,
        )
        self.context_encoder = nn.TransformerEncoder(layer, num_layers=config.num_layers)
        self.pool_query = nn.Parameter(torch.randn(config.d_model) / config.d_model**0.5)
        self.low_rank_u = nn.Linear(config.d_model, config.low_rank, bias=False)
        self.low_rank_v = nn.Linear(config.d_model, config.low_rank, bias=False)
        self.structured_head = nn.Sequential(
            nn.Linear(config.structured_dim, 32),
            nn.GELU(),
            nn.Linear(32, 1),
        )
        # Deterministic by default; training scripts opt back into .train().
        self.eval()

    def forward(
        self,
        region_tokens: torch.Tensor,
        mask: torch.Tensor,
        candidate: torch.Tensor,
        structured: torch.Tensor,
    ) -> torch.Tensor:
        encoded = self.context_encoder(
            self.input_projection(region_tokens),
            src_key_padding_mask=mask,
        )
        context = masked_attention_pool(encoded, mask, self.pool_query)
        candidate_projected = self.input_projection(candidate)
        compatibility = (
            self.low_rank_u(context) * self.low_rank_v(candidate_projected)
        ).sum(dim=-1)
        return compatibility + self.structured_head(structured).squeeze(-1)


def trainable_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def save_checkpoint(
    model: PocketRankContext, config: LadderConfig, directory: str | Path
) -> None:
    from safetensors.torch import save_file

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    save_file(model.state_dict(), str(directory / "model.safetensors"))
    (directory / "config.json").write_text(json.dumps(asdict(config), indent=2))
    (directory / "model_card.json").write_text(
        json.dumps(
            {
                "id": model.model_id,
                "trainable_parameters": trainable_parameters(model),
                "parameter_budget": PARAMETER_BUDGET,
            },
            indent=2,
        )
    )


def load_checkpoint(directory: str | Path) -> tuple[PocketRankContext, LadderConfig]:
    from safetensors.torch import load_file

    directory = Path(directory)
    config = LadderConfig(**json.loads((directory / "config.json").read_text()))
    model = PocketRankContext(config)
    model.load_state_dict(load_file(str(directory / "model.safetensors")))
    model.eval()
    return model, config
