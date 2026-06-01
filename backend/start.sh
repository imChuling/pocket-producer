#!/bin/bash

# Start MongoDB MCP server in background on port 8081
export MDB_MCP_CONNECTION_STRING="$MONGODB_CONNECTION_STRING"
mongodb-mcp-server --transport http --httpHost 0.0.0.0 --httpPort 8081 &
MCP_PID=$!

# Wait for MCP server to be ready
for i in $(seq 1 10); do
  if curl -s http://127.0.0.1:8081/mcp > /dev/null 2>&1; then
    echo "MongoDB MCP server ready on port 8081"
    break
  fi
  sleep 1
done

# Start FastAPI app
exec uvicorn api.main:app --host 0.0.0.0 --port $PORT
