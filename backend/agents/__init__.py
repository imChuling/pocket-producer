"""Pocket Producer agent pipeline.

Active agents in the ingest pipeline:
- Producer (root) → Memory (sub_agent)

Tagging is not an agent: the capture flow calls Gemini directly
(api/pipeline/tagging.py) to keep ingest latency down.
"""

from ._runner import group_fragment_with_agents  # noqa: F401
from .memory import memory_agent  # noqa: F401
from .producer import producer_agent  # noqa: F401
