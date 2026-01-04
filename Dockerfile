# Build Stage
FROM python:3.12-slim AS builder

WORKDIR /app


# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
# --frozen: Use uv.lock for exact versions
# --no-install-project: Do not install the project itself yet (just deps)
RUN uv sync --frozen --no-install-project

# Runtime Stage
FROM python:3.12-slim

WORKDIR /app

# Copy environment from builder
# We copy the entire virtual environment
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Environment variables
# Make sure we use the virtual environment's python and binaries
ENV PATH="/app/.venv/bin:$PATH"

# Run application
# Listen on all interfaces (0.0.0.0)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
