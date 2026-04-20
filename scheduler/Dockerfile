FROM nikolaik/python-nodejs:python3.12-nodejs22@sha256:ba34d3dc43ac5a9ff86da1f74e526bd1dab45b5aa1b2e16ced4b8d3d9ca19166
# Note: nikolaik image provides both Python 3.12 and Node.js 22 LTS.
# Digest pinned 2026-04-20 (captured via Docker Hub registry API, not `docker pull`).
# nikolaik is labeled "experimental" — the digest pin prevents silent base image drift.
# To refresh when nikolaik republishes tag:
#   TOKEN=$(curl -s 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:nikolaik/python-nodejs:pull' | jq -r .token)
#   curl -sI -H "Authorization: Bearer $TOKEN" -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
#     https://registry-1.docker.io/v2/nikolaik/python-nodejs/manifests/python3.12-nodejs22 | grep -i docker-content-digest

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
