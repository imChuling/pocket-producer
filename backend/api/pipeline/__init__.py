"""Pipeline package: fragment processing, tagging, validation, and agent grouping.

Re-exports preserve backward-compatible ``from .pipeline import X`` usage.
"""

from .._clients import get_genai_client
from .grouping import generate_next_action_for_project as _generate_next_action
from .grouping import memory_and_project, run_agent
from .processing import process_fragment_background
from .tagging import build_fallback_tags, tag_fragment_direct
from .validation import validate_audio_upload

__all__ = [
    "get_genai_client",
    "process_fragment_background",
    "validate_audio_upload",
    "memory_and_project",
    "tag_fragment_direct",
    "build_fallback_tags",
    "_generate_next_action",
    "run_agent",
]
