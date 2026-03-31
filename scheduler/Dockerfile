FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv
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

# No EXPOSE — scheduler worker has no HTTP port

# Entry point: run the scheduler worker directly
CMD ["uv", "run", "python", "worker.py"]
