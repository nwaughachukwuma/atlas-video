# ─────────────────────────────────────────────────────────────────────────────
# Atlas — Production multi-arch image
# Docker Hub: nwaughachukwuma/atlas-video
#
# Pull & run (zero setup):
#   docker pull nwaughachukwuma/atlas-video
#   docker run --rm -it \
#     -e GEMINI_API_KEY="$GEMINI_API_KEY" \
#     -e GROQ_API_KEY="$GROQ_API_KEY" \
#     -v atlas-data:/home/atlas/.atlas \
#     nwaughachukwuma/atlas-video extract /data/my-video.mp4
#
# Platforms: linux/amd64, linux/arm64
# ─────────────────────────────────────────────────────────────────────────────

# ── Web UI build stage ───────────────────────────────────────────────────────
FROM node:22-slim AS ui-builder

WORKDIR /build/webui
COPY webui/package*.json ./
RUN npm ci --prefer-offline
COPY webui/ ./
RUN npm run build

# ── Build stage: compile wheel from source ───────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy only the files needed to build the package
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Overlay the pre-built UI assets into the package source tree
COPY --from=ui-builder /build/webui/dist ./src/ui

RUN pip install --no-cache-dir build \
 && python -m build --wheel --outdir /dist

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Atlas"
LABEL org.opencontainers.image.description="Multimodal video understanding engine — extract, index, search, chat"
LABEL org.opencontainers.image.source="https://github.com/nwaughachukwuma/atlas-video"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# ── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# ── Non-root user ────────────────────────────────────────────────────────────
RUN useradd --create-home --shell /bin/bash atlas
USER atlas
WORKDIR /home/atlas

# ── Install atlas wheel ──────────────────────────────────────────────────────
COPY --chown=atlas:atlas --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir --user /tmp/*.whl \
 && rm /tmp/*.whl

# Ensure ~/.local/bin (pip --user scripts) is on PATH
ENV PATH="/home/atlas/.local/bin:${PATH}"

# ── 12-factor configuration (all via ENV) ───────────────────────────────────
# Pass secrets at runtime — never bake them into the image:
#   docker run -e GEMINI_API_KEY="..." -e GROQ_API_KEY="..." ...
# Optional — set to "true" to enable verbose logging:
ENV ENABLE_LOGGING="false"

# ── Persistent data directories ────────────────────────────────────────────
# Pre-create every subdirectory that Atlas writes to so that Docker volume
# initialisation copies them with atlas:atlas ownership.  This must happen
# BEFORE the VOLUME declaration — Docker only seeds a fresh volume from the
# image contents, and only if those contents already exist with the right owner.
RUN mkdir -p \
    /home/atlas/.atlas/index \
    /home/atlas/.atlas/queue/queued_tasks/results \
    && chmod -R 775 /home/atlas/.atlas

# Mount a named volume here so indexed data survives container restarts:
#   docker run -v atlas-data:/home/atlas/.atlas ...
VOLUME ["/home/atlas/.atlas"]

# Atlas HTTP server default port (used by docker run [OPTIONS] and by `atlas serve`).
EXPOSE 8000

# ── Entrypoint ───────────────────────────────────────────────────────────────
COPY --chown=atlas:atlas docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["serve", "-H", "0.0.0.0", "-p", "8000"]
