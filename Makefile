# Name of your running dev container — override via env or CLI:
#   CONTAINER_NAME=my_atlas make docker-test
#   make docker-test CONTAINER_NAME=my_atlas
CONTAINER_NAME ?= atlas-video
IMAGE         = nwaughachukwuma/atlas-video
VERSION      ?= $(shell python3 -c "import re; m=re.search(r'version\s*=\s*\"([^\"]+)\"', open('pyproject.toml').read()); print(m.group(1))" 2>/dev/null || echo "dev")
PLATFORM     ?= linux/amd64,linux/arm64

# ── Web UI ────────────────────────────────────────────────────────────────────
# Build the Svelte web UI and copy the assets into the Python package
build-ui:
	cd webui && npm ci --prefer-offline && npm run build
	rm -rf src/ui
	cp -r webui/dist src/ui

# Start the Svelte dev server with HMR (proxy API to localhost:8000)
dev-ui:
	cd webui && npm run dev

# ── Tests ────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -vv

no-e2e-test:
	pytest tests/ -vv -m "not zvec"



# ── Docker: local development ────────────────────────────────────────────────

# Run tests inside the running dev container
docker-test:
	docker exec -it $(CONTAINER_NAME) bash -c "cd /home/atlas && source .venv/bin/activate && pytest tests/ -vv && deactivate"

# ── Docker: production image ─────────────────────────────────────────────────

# Build production image for the current platform only (fast local build)
docker-build:
	docker build \
		--tag $(IMAGE):$(VERSION) \
		--tag $(IMAGE):latest \
		--label org.opencontainers.image.version=$(VERSION) \
		.

# Build multi-arch image using BuildKit and push to Docker Hub
# Requires: docker login && docker buildx create --use
docker-push:
	docker buildx build \
		--platform $(PLATFORM) \
		--tag $(IMAGE):$(VERSION) \
		--tag $(IMAGE):latest \
		--label org.opencontainers.image.version=$(VERSION) \
		--push \
		.

	@echo ""
	@echo "✅ Pushed $(IMAGE):$(VERSION) ($(PLATFORM))"

# Run atlas with API keys from the local shell environment
docker-run:
	docker run --rm -it \
		-p 8000:8000 \
		--env-file=.env \
		-v atlas-data:/home/atlas/.atlas \
		atlas-video-x1:latest

# Usage: make docker-run CMD="extract /data/video.mp4"
docker-run-cmd:
	docker run --rm -it \
		-p 8000:8000 \
		--env-file=.env \
		-v atlas-data:/home/atlas/.atlas \
		$(IMAGE):latest $(CMD)

# Open a shell inside the production image for debugging
docker-shell:
	docker run --rm -it \
		-e GEMINI_API_KEY="$${GEMINI_API_KEY}" \
		-e GROQ_API_KEY="$${GROQ_API_KEY}" \
		-v atlas-data:/home/atlas/.atlas \
		--entrypoint bash \
		$(IMAGE):latest

.PHONY: build-ui dev-ui test test-all docker-test docker-build docker-push docker-run docker-shell