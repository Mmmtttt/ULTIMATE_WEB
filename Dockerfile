# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS frontend-builder

ARG APP_VERSION=0.0.0
ENV VITE_APP_VERSION=${APP_VERSION} \
    ULTIMATE_APP_VERSION=${APP_VERSION}

WORKDIR /build/comic_frontend

COPY comic_frontend/package*.json ./
RUN npm ci

COPY comic_frontend/ ./
RUN npm run build


FROM python:3.11-slim-bookworm AS runtime

ARG APP_VERSION=0.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ULTIMATE_APP_VERSION=${APP_VERSION} \
    SERVER_CONFIG_PATH=/app/server_config.json \
    RAR_BACKEND_MODE=auto \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=5000 \
    BACKEND_DEBUG=0

WORKDIR /app

LABEL org.opencontainers.image.title="ultimate-web" \
      org.opencontainers.image.version="${APP_VERSION}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        p7zip-full \
        unrar-free \
    && rm -rf /var/lib/apt/lists/*

COPY comic_backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY comic_backend/ /app/comic_backend/
COPY config_templates/ /app/config_templates/
COPY --from=frontend-builder /build/comic_frontend/dist /app/comic_frontend/dist

EXPOSE 5000

CMD ["python", "comic_backend/app.py"]
