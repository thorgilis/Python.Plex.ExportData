# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install cron for scheduling
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app /app/app
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/run-etl.sh /usr/local/bin/run-etl.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/run-etl.sh

# Default: run once unless CRON_SCHEDULE is set
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]


