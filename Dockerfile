# Scrapling + Chromium browsers are preinstalled in the official image.
ARG SCRAPLING_BASE_IMAGE=ghcr.io/d4vinci/scrapling:latest
FROM ${SCRAPLING_BASE_IMAGE}

WORKDIR /service

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-app.txt .
RUN uv pip install --python /app/.venv/bin/python --no-cache -r requirements-app.txt

COPY . .

EXPOSE 8000

ENTRYPOINT []
CMD ["sh", "-c", "uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
