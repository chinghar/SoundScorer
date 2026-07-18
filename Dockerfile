# Single combined image: FastAPI backend + Next.js frontend (standalone) + Caddy reverse
# proxy, run as three processes in one container. See docker-entrypoint.sh and Caddyfile.

# ---- Frontend build ----
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Baked in at build time: same-origin relative API calls, since Caddy proxies
# /songs/* to the backend on the same host/port the frontend is served from.
ENV NEXT_PUBLIC_API_BASE_URL=""
RUN npm run build

# ---- Caddy binary (copied, not apt-installed, to avoid an external repo at build time) ----
FROM caddy:2 AS caddy-bin

# ---- Final image ----
FROM python:3.11-slim

# Node.js runtime for the Next.js standalone server. bash is required by
# docker-entrypoint.sh (uses `wait -n`, a bash builtin not in POSIX sh/dash).
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg bash \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y curl gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=caddy-bin /usr/bin/caddy /usr/local/bin/caddy

# Backend
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
RUN mkdir -p /app/backend/storage/songs

# Frontend (standalone output)
WORKDIR /app/frontend
COPY --from=frontend-builder /app/frontend/.next/standalone ./
COPY --from=frontend-builder /app/frontend/.next/static ./.next/static
COPY --from=frontend-builder /app/frontend/public ./public

# Reverse proxy + startup
COPY Caddyfile /etc/caddy/Caddyfile
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 80
VOLUME ["/app/backend/storage"]
CMD ["/app/docker-entrypoint.sh"]
