# =============================================================================
# Second Brain — API Dockerfile
# Base: python:3.12-slim (NOT Alpine — C extensions require glibc; see CLAUDE.md)
# Build tool: uv (10-100x faster than pip; reproducible via uv.lock)
# Secrets: NEVER baked in — no COPY .env, no secret ENV lines
#           Secrets reach the container only at runtime via docker-compose env_file
# User hardening: deferred to Phase 7 per SKELETON.md scope
# =============================================================================

FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Install uv — the project's package manager
# Using pip install here because uv itself is not in pyproject.toml (it IS the installer)
RUN pip install --no-cache-dir uv

# Copy dependency manifests first to leverage Docker layer caching.
# uv.lock pins every transitive dependency for reproducible builds.
# Changing source files won't invalidate this layer unless deps change.
COPY pyproject.toml uv.lock ./

# Install runtime dependencies from the lockfile (frozen = no network resolution)
# --no-dev excludes ruff/mypy/pytest/httpx from the production image
RUN uv sync --frozen --no-dev

# Copy application source code
# .dockerignore excludes .env, .venv/, .git/, caches, and planning files
COPY app/ ./app/

# Expose the port uvicorn listens on
EXPOSE 8000

# Run the FastAPI app via uvicorn
# --host 0.0.0.0 required inside Docker (default 127.0.0.1 is unreachable from host)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
