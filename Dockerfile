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

# Generate seed data from SQL
RUN python convert_sql.py

# Create ChromaDB data directory and cache directories with correct permissions
RUN mkdir -p /app/chroma_data /app/.cache/huggingface && chown -R appuser:appuser /app

# Environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV HOME="/app"
ENV TRANSFORMERS_CACHE="/app/.cache/huggingface"
ENV HF_HOME="/app/.cache/huggingface"

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check (using Python since curl is not available in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run application
# Listen on all interfaces (0.0.0.0)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
