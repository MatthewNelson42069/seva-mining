FROM nikolaik/python-nodejs:python3.12-nodejs22
# Note: nikolaik image provides both Python 3.12 and Node.js 22 LTS.
# IMPORTANT: pin to a sha256 digest after first successful build to prevent image drift.
# nikolaik is labeled "experimental" — pinning prevents silent base image breakage.
# After local Docker build succeeds, run:
#   docker image inspect nikolaik/python-nodejs:python3.12-nodejs22 --format='{{.Id}}'
# Then replace this line with:
#   FROM nikolaik/python-nodejs@sha256:<digest>  # was: python3.12-nodejs22
# (RESEARCH.md Pitfall 7 — digest-pin is required before production deploy)
# TODO: operator must run the above command after first successful Docker build and update this line.

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy dependency spec first (layer caching)
COPY pyproject.toml .
COPY uv.lock* .

# Install production dependencies only
RUN uv sync --no-dev

# Install chart renderer Node dependencies + download fonts
# Railway build context is the repo root — COPY paths are relative to repo root.
COPY scheduler/chart_renderer/ ./chart_renderer/
WORKDIR /app/chart_renderer
RUN npm ci --production
RUN sh download-fonts.sh
WORKDIR /app

# Copy scheduler source files
COPY scheduler/worker.py .
COPY scheduler/config.py .
COPY scheduler/database.py .
COPY scheduler/agents/ ./agents/
COPY scheduler/models/ ./models/
COPY scheduler/services/ ./services/

# No EXPOSE — scheduler worker has no HTTP port

# Entry point: run the scheduler worker directly
CMD ["/app/.venv/bin/python", "worker.py"]
