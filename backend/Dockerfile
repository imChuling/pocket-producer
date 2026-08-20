FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Pinned to match the standalone mongodb-mcp service and avoid
# @latest protocol/endpoint drift between builds.
RUN npm install -g mongodb-mcp-server@1.10.0

WORKDIR /app

RUN pip install uv

COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

COPY agents/ ./agents/
COPY tools/ ./tools/
COPY api/ ./api/
COPY jobs/ ./jobs/
COPY skills/ ./skills/
COPY ranking/ ./ranking/
COPY artifacts/ ./artifacts/
COPY start.sh ./

RUN chmod +x start.sh

ENV PORT=8000
ENV ENABLE_MCP_MEMORY_TOOLS=1
ENV MCP_SERVER_URL=http://127.0.0.1:8081/mcp
EXPOSE 8000
CMD ["./start.sh"]
