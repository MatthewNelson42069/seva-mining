FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency spec first (layer caching)
COPY scheduler/pyproject.toml .
COPY scheduler/uv.lock* .

# Install production dependencies only
RUN uv sync --no-dev

# Copy scheduler source files
COPY scheduler/worker.py .
COPY scheduler/config.py .
COPY scheduler/database.py .
COPY scheduler/agents/ ./agents/
COPY scheduler/models/ ./models/

# No EXPOSE — scheduler worker has no HTTP port

# Entry point: run the scheduler worker directly
CMD ["uv", "run", "python", "worker.py"]
