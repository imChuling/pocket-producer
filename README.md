# Pocket Producer

Pocket Producer is an agentic creative memory system for music makers. It captures
small fragments, reconnects them with past ideas, and suggests a concrete next
step for unfinished projects.

## Architecture

The ingest flow intentionally separates latency-sensitive perception from
agentic memory work:

1. **Fast capture/tagging path**: FastAPI stores the fragment, uploads audio to
   Cloud Storage, and uses Gemini multimodal tagging with the local music skills.
2. **Agentic memory path**: after an embedding exists, the ADK `Project Memory`
   agent performs vector search, relationship reasoning, project grouping,
   project updates, Rescue Score refresh, and next-action generation.

This keeps capture responsive while making the product's core value path an
actual agent workflow.

## ADK and MongoDB MCP Path

The demonstrable agent path lives in
`backend/services/project_memory_agent.py`.

The agent uses scoped business tools for all writes:

- `get_fragment_context`
- `vector_search_fragment_neighbors`
- `get_project_context`
- `create_project_from_fragments`
- `attach_fragment_to_project`
- `refresh_project_score`

Every tool binds database access to the authenticated `user_id`. The older
generic ADK Mongo tools in `backend/tools/mongodb.py` now have a collection
allowlist and require user-scoped filters.

MongoDB MCP read tools can be enabled for demo/deployment with:

```bash
ENABLE_MCP_MEMORY_TOOLS=1
MCP_SERVER_URL=http://localhost:8081/mcp
```

Project writes still go through scoped business tools, so the agent can be
MCP-aware without receiving arbitrary database write access.

### How to verify the ADK + MCP path (for judges)

This path is on the **default** ingest pipeline — every fragment with an
embedding triggers the agent (`main.py` → `_process_fragment_background` →
`_memory_and_project` → `group_fragment_with_agent`). To see it directly:

1. **Confirm the path is live and MCP is on.** With the stack running
   (`docker compose up`, which sets `ENABLE_MCP_MEMORY_TOOLS=1`):

   ```bash
   curl -H "Authorization: Bearer <id-token>" \
     http://localhost:8000/api/agent-memory/status
   # -> mcp_read_tools_enabled: true, mcp_server_url_configured: true
   ```

2. **Watch the agent reason in the logs.** Ingest a fragment (or call
   `POST /api/fragments/{id}/group-with-agent`) and tail the backend logs:

   ```bash
   docker compose logs -f backend | grep ProjectMemory
   ```

   Expect:
   - `ProjectMemory: mounting read-only MongoDB MCP toolset (prefix=mongo_mcp) ...`
     (proves the MCP toolset is attached at startup)
   - `ProjectMemory tool call: agent=project_memory tool=vector_search_fragment_neighbors`
     then `... tool=create_project_from_fragments` / `attach_fragment_to_project`
     (proves multi-step vector search → relationship reasoning → grouping)

3. **See the decision in the UI.** Grouped fragment cards now render a
   **"Memory Agent linked this"** block showing the agent's `connection_reason`
   and `connection_types` — the multi-step reasoning made visible, not just tags.

Useful demo endpoints:

- `GET /api/agent-memory/status` — reports ADK path + MCP enablement
- `POST /api/fragments/{fragment_id}/group-with-agent` — run the agent on demand
- `POST /api/reprocess-projects` — re-group existing fragments

## Data Safety

- Firebase Auth verifies every user request.
- User-owned document reads and writes include `user_id` filters.
- Fragment deletion removes both the MongoDB document and the associated GCS
  audio object.
- Audio streams are served through authenticated API endpoints, not public GCS
  URLs.

## Local Development

Backend:

```bash
cd backend
.venv/bin/python -m pytest tests/test_rescue_score.py
uvicorn api.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```
