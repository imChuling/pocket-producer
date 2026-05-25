import os

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from tools.mongodb import count_documents, find_documents, vector_search

from ._skills_loader import get_skill_toolset

MEMORY_INSTRUCTION = """\
You are the Memory Agent (Grounding layer) of Pocket Producer.

Given a new fragment's embedding and user_id, use the vector_search tool
to find similar past fragments in the "fragments" collection.

For each candidate neighbor, apply the relationship-rules skill to classify
the relationship:
- same_song_candidate
- related_theme
- similar_emotion
- unrelated

Use the musical-knowledge skill (key-compatibility + tempo-rules) when
evaluating musical_compatibility signal.

Use the refusal-rules skill when confidence is low or signals conflict.

Output structured JSON per the relationship-rules skill's schema, including
your suggested_action (join_project / bridge_projects / new_project /
needs_user_confirmation).

Conservative bias: when uncertain, choose the WEAKER relationship type.
False positives damage user trust more than false negatives.

== Available tools ==
- vector_search(collection, query_vector, user_id, limit) — $vectorSearch
- find_documents(collection, filter, limit) — read documents
- count_documents(collection, filter) — count documents

== Boundaries (what you do NOT do) ==
- Do NOT write to the database
- Do NOT make creative decisions or suggestions
- Do NOT communicate directly with the user
- Do NOT tag or re-tag fragments
"""

memory_agent = LlmAgent(
    name="memory",
    model=os.environ.get("MEMORY_MODEL", "gemini-2.5-flash"),
    instruction=MEMORY_INSTRUCTION,
    tools=[
        get_skill_toolset(["relationship-rules", "musical-knowledge", "refusal-rules"]),
        FunctionTool(vector_search),
        FunctionTool(find_documents),
        FunctionTool(count_documents),
    ],
)
