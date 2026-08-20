# ORION Dockerfile — simulation and development
# Multi-stage build for ORION Physical Intelligence OS
# License: Apache 2.0

FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy project config first for better caching
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source code
COPY src/ ./src/
COPY simulation/ ./simulation/
COPY tests/ ./tests/
COPY docs/ ./docs/

# Set Python path
ENV PYTHONPATH=/app
ENV ORION_ENV=docker

# Default command — run tests
CMD ["pytest", "--tb=short", "-q", "-m", "not live"]
