"""L1 of the capacity ladder: mean-pooled DeepSets over region tokens."""

import torch
from torch import nn

from ranking.context_model import LadderConfig


class DeepSetsRanker(nn.Module):
    model_id = "deepsets-v1"

    def __init__(self, config: LadderConfig):
        super().__init__()
        self.config = config
        self.phi = nn.Sequential(
            nn.Linear(config.input_dim, config.d_model),
            nn.GELU(),
        )
        self.candidate_projection = nn.Linear(config.input_dim, config.d_model)
        self.rho = nn.Sequential(
            nn.Linear(config.d_model * 2 + config.structured_dim, config.d_model),
            nn.GELU(),
            nn.Linear(config.d_model, 1),
        )
        self.eval()

    def forward(
        self,
        region_tokens: torch.Tensor,
        mask: torch.Tensor,
        candidate: torch.Tensor,
        structured: torch.Tensor,
    ) -> torch.Tensor:
        encoded = self.phi(region_tokens)
        keep = (~mask).unsqueeze(-1).to(encoded.dtype)
        pooled = (encoded * keep).sum(dim=1) / keep.sum(dim=1).clamp(min=1.0)
        features = torch.cat(
            [pooled, self.candidate_projection(candidate), structured], dim=-1
        )
        return self.rho(features).squeeze(-1)
