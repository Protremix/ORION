# ORION Dockerfile — simulation and development
# Multi-stage build for ORION Physical Intelligence OS
# License: Apache 2.0

FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r orion -g 1000 && \
    useradd -r -g orion -u 1000 -s /bin/bash -d /app orion

# Set work directory
WORKDIR /app

# Copy project config and source first for editable install
COPY --chown=orion:orion pyproject.toml ./
COPY --chown=orion:orion src/ ./src/
COPY --chown=orion:orion simulation/ ./simulation/
COPY --chown=orion:orion README.md ./

# Install dependencies (editable install requires source to be present)
RUN pip install --no-cache-dir -e ".[dev]"

# Copy remaining files with proper ownership
COPY --chown=orion:orion tests/ ./tests/
COPY --chown=orion:orion docs/ ./docs/
COPY --chown=orion:orion conftest.py ./

# Set Python path
ENV PYTHONPATH=/app
ENV ORION_ENV=docker

# Switch to non-root user (least privilege)
USER orion

# Default command
CMD ["python", "-m", "pytest", "-q", "-m", "not live", "--tb=short"]
