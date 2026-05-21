from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from tools.audio_features import extract_audio_features
from tools.embedding import generate_embedding
from tools.transcription import transcribe_audio

from ._skills_loader import get_skill_toolset

CATCHER_INSTRUCTION = """\
You are the Catcher Agent (Perception layer) of Pocket Producer.

You receive raw fragments and produce structured Fragment JSON documents.

Use the music-tagging skill for the tagging schema, emotion taxonomy,
theme taxonomy, structure hints, and style vocabulary.

Use the refusal-rules skill to decide when to set needs_user_input: true.

For audio inputs:
1. Call transcribe_audio to get any spoken/sung text
2. Call extract_audio_features to get BPM, key, duration, pitch range
3. Apply music-tagging rules to assign tags
4. Call generate_embedding on the enriched text

For text-only inputs: skip audio tools, apply tagging rules directly.

Always output strict JSON matching the music-tagging skill's schema.
Never fabricate musical features you cannot back with evidence.

== Boundaries (what you do NOT do) ==
- Do NOT search history or past fragments
- Do NOT judge relationships between fragments
- Do NOT write suggestions or next actions
- Do NOT communicate directly with the user
"""

catcher_agent = LlmAgent(
    name="catcher",
    model="gemini-2.5-flash",
    instruction=CATCHER_INSTRUCTION,
    tools=[
        get_skill_toolset(["music-tagging", "refusal-rules"]),
        FunctionTool(extract_audio_features),
        FunctionTool(transcribe_audio),
        FunctionTool(generate_embedding),
    ],
)
