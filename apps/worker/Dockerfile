# Stage 1: Build dependencies
FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock* ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.12-slim as runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root unprivileged worker user
RUN useradd -m -u 1000 worker && chown -R worker:worker /app

COPY --from=builder /root/.local /home/worker/.local
ENV PATH=/home/worker/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY --chown=worker:worker . .

USER worker

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "from apps.worker.celery import celery_app; celery_app.control.ping(timeout=2.0)" || exit 1

CMD ["celery", "-A", "apps.worker.celery", "worker", "--loglevel=info"]