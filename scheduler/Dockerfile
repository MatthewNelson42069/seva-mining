# Pure-Python scheduler image. Railway scheduler service Root Directory = scheduler/,
# so all COPY paths are relative to scheduler/ (NO `scheduler/` prefix — quick-t78 `bbc6e6a` lesson).
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy dependency spec first (layer caching)
COPY pyproject.toml .
COPY uv.lock* .

# Install production dependencies only
RUN uv sync --no-dev

# Copy scheduler source files
COPY worker.py .
COPY config.py .
COPY database.py .
COPY agents/ ./agents/
COPY models/ ./models/
COPY services/ ./services/
COPY seed_content_data.py .
COPY seed_twitter_data.py .

# No EXPOSE — scheduler worker has no HTTP port

CMD ["/app/.venv/bin/python", "worker.py"]
