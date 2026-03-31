FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency spec first (layer caching — only reinstall when pyproject.toml changes)
COPY pyproject.toml .
COPY uv.lock* .

# Install production dependencies only (no dev extras)
RUN uv sync --no-dev

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Run Alembic migrations then start server.
# --workers 1 required for Neon free tier connection limits (D-09).
# $PORT provided by Railway.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
