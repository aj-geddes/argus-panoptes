---
title: "Deployment"
description: "Production deployment with Docker, PostgreSQL, and security hardening for Argus Panoptes."
layout: page
---

## Docker Production

The production Docker image uses a multi-stage build, runs as a non-root user,
and includes a health check.

```bash
# Build the production image
docker build -t argus-panoptes:latest -f docker/Dockerfile .

# Run with SQLite (single-node, simplest)
docker run -d \
  --name argus \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v argus-data:/app/data \
  --restart unless-stopped \
  argus-panoptes:latest

# Run with PostgreSQL and API key
docker run -d \
  --name argus \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://argus:secret@postgres:5432/argus" \
  -e ARGUS_API_KEY="your-strong-secret-key" \
  -v $(pwd)/config:/app/config \
  --restart unless-stopped \
  argus-panoptes:latest
```

---

## Docker Compose — Development

The development Compose file mounts source code and enables hot-reload:

```yaml
# docker/docker-compose.yml
services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ../src:/app/src
      - ../config:/app/config
      - ../static:/app/static
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./argus.db
    command: uvicorn argus.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src
```

Start it:

```bash
cd docker
docker compose up
```

---

## Docker Compose — Production with PostgreSQL

```yaml
# docker-compose.prod.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: argus
      POSTGRES_USER: argus
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U argus"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  argus:
    image: argus-panoptes:latest
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://argus:${POSTGRES_PASSWORD}@postgres:5432/argus"
      ARGUS_API_KEY: "${ARGUS_API_KEY}"
    volumes:
      - ./config:/app/config
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres-data:
```

```bash
# Create a .env file
cat > .env << EOF
POSTGRES_PASSWORD=change-me-strong-password
ARGUS_API_KEY=change-me-strong-api-key
EOF

docker compose -f docker-compose.prod.yml up -d
```

---

## PostgreSQL Setup

### Create the database

```bash
psql -U postgres
CREATE USER argus WITH PASSWORD 'your-secure-password';
CREATE DATABASE argus OWNER argus;
GRANT ALL PRIVILEGES ON DATABASE argus TO argus;
```

### Run migrations

```bash
DATABASE_URL="postgresql+asyncpg://argus:password@localhost:5432/argus" \
  alembic upgrade head
```

### Connection pool settings

For production with many concurrent agents, increase the pool size:

```yaml
database:
  url: "postgresql+asyncpg://argus:pass@localhost:5432/argus"
  pool_size: 25
```

---

## Reverse Proxy with Nginx

Place Argus behind Nginx for TLS termination and better request handling:

```nginx
server {
    listen 443 ssl http2;
    server_name argus.example.com;

    ssl_certificate     /etc/ssl/certs/argus.crt;
    ssl_certificate_key /etc/ssl/private/argus.key;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # Required for SSE streaming
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 86400s;
    }
}
```

---

## Security Hardening

### Enable API Key Authentication

```yaml
security:
  api_key_auth:
    enabled: true
    header_name: "X-API-Key"
```

Set the key via environment variable — **never hardcode secrets in config files**:

```bash
ARGUS_API_KEY="$(openssl rand -hex 32)"
```

### Enable Rate Limiting

```yaml
security:
  rate_limiting:
    enabled: true
    requests_per_window: 500
    window_seconds: 60
```

### Non-Root Docker Container

The production Dockerfile already runs as a non-root user (UID 1000).
Verify with:

```bash
docker exec argus whoami
# argus
```

### Network Isolation

Restrict the ingestion endpoint to your internal network with firewall rules:

```bash
# Allow only internal network to reach Argus
ufw allow from 10.0.0.0/8 to any port 8000
ufw deny 8000
```

### Secrets Management

Use Docker secrets or a vault for production credentials:

```bash
# Docker secrets
echo "your-api-key" | docker secret create argus_api_key -

# Reference in Compose
services:
  argus:
    secrets:
      - argus_api_key
    environment:
      ARGUS_API_KEY_FILE: /run/secrets/argus_api_key
```

---

## Health Checks

The `/health` endpoint is suitable for load balancer health checks:

```bash
# Check every 30 seconds, fail after 3 consecutive failures
curl -f http://localhost:8000/health || exit 1
```

Docker Compose health check:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

---

## Resource Requirements

| Deployment | CPU | Memory | Storage |
|------------|-----|--------|---------|
| Single agent, dev | 0.5 vCPU | 256 MB | 1 GB |
| Small team (5-10 agents) | 1 vCPU | 512 MB | 20 GB |
| Medium (10-50 agents) | 2 vCPU | 1 GB | 100 GB |
| Large (50+ agents) | 4+ vCPU | 2+ GB | PostgreSQL |

For large deployments, use PostgreSQL and increase `server.workers` proportional
to available CPU cores.

---

## Monitoring Argus

Argus is itself observable. Use the `/health` endpoint and the metrics API
to monitor the platform:

```bash
# Check service health
curl http://localhost:8000/health

# Check ingestion throughput
curl http://localhost:8000/api/v1/metrics/summary?window=1m
```

Set up an external uptime monitor (e.g., Better Uptime, UptimeRobot) on
`https://argus.example.com/health`.
