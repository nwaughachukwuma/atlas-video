# See this if you use mac x86_64 - Zvec doesn't compile on that arch.
# You can choose to symlink to a volume so changes reflect immediately.
#
# Development Dockerfile — linux/arm64
#
# Build: docker build --platform linux/arm64 -t atlas .
#
# Run (interactive dev shell, source already inside the image):
#   docker run --platform linux/arm64 --rm -it \
#     -v "$(pwd):/root/atlas" \
#     -e GEMINI_API_KEY="$GEMINI_API_KEY" \
#     -e GROQ_API_KEY="$GROQ_API_KEY" \
#     atlas bash
#
# Run a command directly:
#   docker run --platform linux/arm64 --rm -it \
#     -e GEMINI_API_KEY="$GEMINI_API_KEY" \
#     -e GROQ_API_KEY="$GROQ_API_KEY" \
#     atlas transcribe /root/atlas/sample_files/cedar.mp4

FROM --platform=linux/arm64 python:3.12-slim

# ── System dependencies ──────────────────────────────────────────────────────
# ffmpeg: media processing (clipping, audio extraction)
# libgomp1: OpenMP runtime required by some libs / ffmpeg operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Python tooling ───────────────────────────────────────────────────────────
RUN pip install --no-cache-dir uv

# ── App source ───────────────────────────────────────────────────────────────
WORKDIR /root/atlas

COPY . .

RUN uv pip install --system --no-cache -e .

# ── Runtime ──────────────────────────────────────────────────────────────────
# Persist the vector store outside the image layer.
VOLUME ["/root/.atlas"]
ENTRYPOINT ["atlas"]
CMD ["--help"]
