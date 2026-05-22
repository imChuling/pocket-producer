import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ._skills_loader import get_skill_toolset
from .catcher import catcher_agent
from .memory import memory_agent

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8081/mcp")

producer_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url=MCP_SERVER_URL),
    tool_filter=["insert-many", "update", "find"],
)

PRODUCER_INSTRUCTION = """\
You are the Producer Agent (Action layer) — root orchestrator of Pocket
Producer.

For each new fragment:

Step 1: Delegate to Catcher to ingest and tag.
Step 2: Delegate to Memory to find related fragments and classify
        relationships.
Step 3: Based on Memory's suggested_action:
   - join_project: add to existing project
   - bridge_projects: SURFACE THIS (high-value moment for user)
   - new_project: start new project
   - needs_user_confirmation: escalate to user
Step 4: Use rescue-scoring skill to compute or update the affected
        project's Rescue Score.
Step 5: Generate ONE concrete next action (≤ 30 min for user) using
        musical-knowledge skill when relevant.
Step 6: Use MongoDB MCP tools: insert-many (for new fragments) and
        update (for existing projects).

Output a structured response with:
- decision (join / new / bridge)
- project_id
- reasoning (1-2 sentences for the user)
- next_action (specific, doable in 30 min)
- rescue_score (updated)

Use the refusal-rules skill when you cannot decide confidently. When in
doubt, surface options to the user rather than guess.

The user's trust depends on you NOT making confident mistakes. A polite
"I'm not sure, here are two options" is always better than a wrong
confident answer.

== Boundaries (what you do NOT do) ==
- Do NOT tag fragments directly (Catcher does that)
- Do NOT run vector search directly (Memory does that)
- Do NOT generate music or lyrics
- Do NOT judge musical quality or commercial viability
"""

producer_agent = LlmAgent(
    name="producer",
    model="gemini-2.5-pro",
    instruction=PRODUCER_INSTRUCTION,
    sub_agents=[catcher_agent, memory_agent],
    tools=[
        get_skill_toolset(["rescue-scoring", "refusal-rules", "musical-knowledge"]),
        producer_mcp,
    ],
)
