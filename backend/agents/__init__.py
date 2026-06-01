"""Pocket Producer agent pipeline.

Active agents in the ingest pipeline:
- Producer (root) → Memory (sub_agent)

Catcher agent is defined but bypassed in the capture flow — tagging is handled
by a direct Gemini multimodal call for latency optimization. The Catcher agent
is available for full Agent Engine deployment where latency is less critical.
"""

from .memory import memory_agent  # noqa: F401
from .producer import producer_agent  # noqa: F401
from ._runner import group_fragment_with_agents  # noqa: F401
