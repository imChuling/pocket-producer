"""L0 of the capacity ladder: a linear model over interpretable inputs.

Inputs are the structured features plus the cosine between the candidate and
the masked mean of the region tokens — the simplest learnable rung, and the
bar every heavier model must beat.
"""

import torch
from torch import nn

from ranking.context_model import LadderConfig


class LinearRanker(nn.Module):
    model_id = "linear-v1"

    def __init__(self, config: LadderConfig):
        super().__init__()
        self.config = config
        self.head = nn.Linear(config.structured_dim + 1, 1)
        self.eval()

    def forward(
        self,
        region_tokens: torch.Tensor,
        mask: torch.Tensor,
        candidate: torch.Tensor,
        structured: torch.Tensor,
    ) -> torch.Tensor:
        keep = (~mask).unsqueeze(-1).to(region_tokens.dtype)
        context_mean = (region_tokens * keep).sum(dim=1) / keep.sum(dim=1).clamp(
            min=1.0
        )
        cosine = torch.cosine_similarity(context_mean, candidate, dim=-1)
        features = torch.cat([structured, cosine.unsqueeze(-1)], dim=-1)
        return self.head(features).squeeze(-1)
