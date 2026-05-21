FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install uv

COPY pyproject.toml ./
RUN uv pip install --system -e .

COPY skills/ ./skills/
COPY . .

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
