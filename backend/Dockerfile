FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install uv

COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

COPY agents/ ./agents/
COPY tools/ ./tools/
COPY api/ ./api/
COPY jobs/ ./jobs/
COPY skills/ ./skills/

ENV PORT=8000
EXPOSE 8000
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
