import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ._skills_loader import get_skill_toolset

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8081/mcp")

memory_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url=MCP_SERVER_URL),
    tool_filter=["aggregate", "find", "count"],
)

MEMORY_INSTRUCTION = """\
You are the Memory Agent (Grounding layer) of Pocket Producer.

Given a new fragment's embedding and user_id, use the aggregate tool with
a $vectorSearch pipeline stage to find similar past fragments.

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

== Boundaries (what you do NOT do) ==
- Do NOT write to the database
- Do NOT make creative decisions or suggestions
- Do NOT communicate directly with the user
- Do NOT tag or re-tag fragments
"""

memory_agent = LlmAgent(
    name="memory",
    model="gemini-2.5-flash",
    instruction=MEMORY_INSTRUCTION,
    tools=[
        get_skill_toolset(["relationship-rules", "musical-knowledge", "refusal-rules"]),
        memory_mcp,
    ],
)
