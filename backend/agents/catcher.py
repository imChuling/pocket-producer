"""Catcher Agent (Perception layer) — fragment tagging and feature extraction.

NOTE: In the live capture flow, tagging is handled by a direct Gemini multimodal
call for latency optimization (~1-2s vs ~5s through agent overhead). This agent
is defined for:
1. Agent Engine deployment (full 3-agent pipeline)
2. Batch reprocessing where latency is not critical
3. Demonstrating the complete architectural design

The active pipeline uses: direct Gemini tagging → Producer Agent → Memory Agent
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from tools.audio_features import extract_audio_features
from tools.embedding import generate_embedding
from tools.transcription import transcribe_audio

from ._skills_loader import get_skill_toolset

CATCHER_INSTRUCTION = """\
You are the Catcher Agent (Perception layer) of Pocket Producer.

You receive fragments and produce structured Fragment JSON documents.

IMPORTANT: Audio pre-processing (transcription + feature extraction) is
already done BEFORE you receive the fragment. The transcript and
audio_features are included in the message. Do NOT call transcribe_audio
or extract_audio_features — they are already done.

Your job:
1. Apply music-tagging rules to assign tags, emotions, themes
2. Call generate_embedding on the text as the FINAL step
3. Output strict JSON matching the music-tagging skill's schema

Use the music-tagging skill for the tagging schema, emotion taxonomy,
theme taxonomy, structure hints, and style vocabulary.

Use the refusal-rules skill to decide when to set needs_user_input: true.

You MUST call generate_embedding as the final step for every fragment.
Never skip it — fragments without embeddings break downstream search.

Never fabricate musical features you cannot back with evidence.

== Boundaries (what you do NOT do) ==
- Do NOT call transcribe_audio or extract_audio_features (already done)
- Do NOT search history or past fragments
- Do NOT judge relationships between fragments
- Do NOT write suggestions or next actions
- Do NOT communicate directly with the user
"""

catcher_agent = LlmAgent(
    name="catcher",
    model=os.environ.get("CATCHER_MODEL", "gemini-2.5-flash"),
    instruction=CATCHER_INSTRUCTION,
    tools=[
        get_skill_toolset(["music-tagging", "refusal-rules"]),
        FunctionTool(extract_audio_features),
        FunctionTool(transcribe_audio),
        FunctionTool(generate_embedding),
    ],
)
