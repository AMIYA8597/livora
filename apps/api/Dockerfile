# Multi-stage production Dockerfile for FastAPI Backend
# Stage 1: Build dependencies and wheels
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md constraints.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels -c constraints.txt .

# Stage 2: Final hardened minimal runtime image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -r -g 10001 flatmate && \
    useradd -r -u 10001 -g flatmate -s /bin/false -d /app flatmate

COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY . /app
RUN chown -R flatmate:flatmate /app

USER flatmate

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

# WEB_CONCURRENCY processes (one per vCPU, set by the deploy). Keep-alive above the load
# balancer's idle timeout; in-flight requests get 8 s to finish when an instance is stopped.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --timeout-keep-alive 75 --timeout-graceful-shutdown 8 --backlog 2048 --no-server-header"]
