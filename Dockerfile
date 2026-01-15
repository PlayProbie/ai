# Build Stage
FROM python:3.12-slim AS builder

WORKDIR /app


# Install build dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
# --no-dev: Exclude development dependencies (pytest, ruff, etc.)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Runtime Stage
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system appuser && adduser --system --group appuser

# Copy environment from builder
# We copy the entire virtual environment
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Create ChromaDB data directory with correct permissions
RUN mkdir -p /app/chroma_data && chown -R appuser:appuser /app/chroma_data

# Switch to non-root user
USER appuser

# Environment variables
# Make sure we use the virtual environment's python and binaries
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Health check (using Python since curl is not available in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run application
# Listen on all interfaces (0.0.0.0)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
