FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/grobomo/coconut"
LABEL org.opencontainers.image.description="Coconut — Reusable AI Chat Assistant"

WORKDIR /app

# Copy application code
COPY core/ core/
COPY adapters/ adapters/
COPY config/ config/
COPY coconut.py .

# Data directory for cache, health, logs
RUN mkdir -p /app/data
ENV COCONUT_DATA_DIR=/app/data

# Health check — exits 0 if healthy, 1 if stale
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 coconut.py --health

ENTRYPOINT ["python3", "coconut.py"]
