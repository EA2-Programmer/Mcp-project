# TrakSYS MCP + OpenWebUI + Langfuse Setup Guide

Full observability stack: OpenWebUI → LLM → MCP tools → SQL Server, with all traces visible in Langfuse.

---

## Architecture

```
User (OpenWebUI) → LLM (Claude/GPT) → MCP Tools (TrakSYS) → SQL Server (EBR_Template)
                         ↓
                    Langfuse (traces)
```

| Service | URL | Notes |
|---|---|---|
| OpenWebUI | http://localhost:3001 | Chat interface |
| Pipelines | http://localhost:9099 | Langfuse filter pipeline |
| TrakSYS MCP | http://localhost:8000 | MCP server + mcpo proxy |
| Langfuse | http://localhost:3000 | Observability dashboard |
| SQL Server | localhost:1433 | Windows host (NOT in Docker) |

---

## Prerequisites

- Docker Desktop for Windows
- SQL Server on Windows with Mixed Mode authentication enabled
- Anthropic and/or OpenAI API keys

---

## Step 1 — Run Langfuse

Langfuse runs in its own `docker-compose` and must be started **before** the main stack. It creates a Docker network (`langfuse_default`) that other containers will join.

### 1.1 Create Langfuse folder and compose file

Create a folder (e.g. `C:\langfuse`) and inside it create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  langfuse-web:
    image: langfuse/langfuse:3
    container_name: langfuse-langfuse-web-1
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/langfuse
      - NEXTAUTH_SECRET=your-nextauth-secret-change-me
      - SALT=your-salt-change-me
      - NEXTAUTH_URL=http://localhost:3000
      - TELEMETRY_ENABLED=false
      - LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=true
      - CLICKHOUSE_URL=http://clickhouse:8123
      - CLICKHOUSE_USER=clickhouse
      - CLICKHOUSE_PASSWORD=clickhouse
      - REDIS_HOST=redis
      - MINIO_ENDPOINT=minio
      - MINIO_PORT=9000
      - MINIO_ACCESS_KEY_ID=minio
      - MINIO_SECRET_ACCESS_KEY=miniosecret
      - MINIO_BUCKET_NAME=langfuse
    depends_on:
      postgres:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    networks:
      - langfuse_default

  langfuse-worker:
    image: langfuse/langfuse-worker:3
    container_name: langfuse-langfuse-worker-1
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/langfuse
      - CLICKHOUSE_URL=http://clickhouse:8123
      - CLICKHOUSE_USER=clickhouse
      - CLICKHOUSE_PASSWORD=clickhouse
      - REDIS_HOST=redis
      - MINIO_ENDPOINT=minio
      - MINIO_PORT=9000
      - MINIO_ACCESS_KEY_ID=minio
      - MINIO_SECRET_ACCESS_KEY=miniosecret
      - MINIO_BUCKET_NAME=langfuse
      - SALT=your-salt-change-me
    depends_on:
      postgres:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - langfuse_default

  postgres:
    image: postgres:17
    container_name: langfuse-postgres-1
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=langfuse
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - langfuse_default

  redis:
    image: redis:7
    container_name: langfuse-redis-1
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - langfuse_default

  clickhouse:
    image: clickhouse/clickhouse-server
    container_name: langfuse-clickhouse-1
    environment:
      - CLICKHOUSE_USER=clickhouse
      - CLICKHOUSE_PASSWORD=clickhouse
    volumes:
      - clickhouse-data:/var/lib/clickhouse
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8123/ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - langfuse_default

  minio:
    image: cgr.dev/chainguard/minio
    container_name: langfuse-minio-1
    ports:
      - "9090:9000"
      - "9091:9001"
    environment:
      - MINIO_ROOT_USER=minio
      - MINIO_ROOT_PASSWORD=miniosecret
    command: sh -c "mkdir -p /data/langfuse && minio server /data --console-address ':9001'"
    volumes:
      - minio-data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - langfuse_default

volumes:
  postgres-data:
  clickhouse-data:
  minio-data:

networks:
  langfuse_default:
    driver: bridge
```

### 1.2 Start Langfuse

```powershell
cd C:\langfuse
docker compose up -d

# Wait ~30 seconds for all services to be healthy, then verify
docker ps
```

All containers should show `healthy`: `langfuse-langfuse-web-1`, `langfuse-postgres-1`, `langfuse-redis-1`, `langfuse-clickhouse-1`, `langfuse-minio-1`.

### 1.3 Create your Langfuse account and get API keys

1. Open **http://localhost:3000**
2. Click **Sign Up** and create an account
3. Create a new **Organization** and **Project**
4. Go to **Project Settings → API Keys**
5. Click **Create API Key** — copy both:
   - `sk-lf-...` → Secret Key
   - `pk-lf-...` → Public Key

> ⚠️ Save these keys — you will need them in the `.env` file and in OpenWebUI pipeline valves.

---

## Step 2 — SQL Server Setup

> ⚠️ This is the most common failure point. Do this first before touching Docker.

### Enable Mixed Mode Authentication

1. Open **SQL Server Management Studio** or run in IntelliJ with Windows Auth:

```sql
-- Check current auth mode (must return 0 for Mixed Mode)
SELECT SERVERPROPERTY('IsIntegratedSecurityOnly');
-- 0 = Mixed Mode ✅
-- 1 = Windows Auth only ❌ (need to fix)
```

2. If result is `1`, enable Mixed Mode via registry:

```powershell
# Run as Administrator
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL16.MSSQLSERVER\MSSQLServer" `
  -Name LoginMode -Value 2

# CRITICAL: Must restart the service for the change to take effect
Stop-Service -Name MSSQLSERVER -Force
Start-Service -Name MSSQLSERVER
```

3. Verify the restart applied it:

```sql
SELECT SERVERPROPERTY('IsIntegratedSecurityOnly');
-- Must now return 0
```

### Create a SQL Login

```sql
-- Create the login
CREATE LOGIN traksys_app WITH PASSWORD = 'YourPassword99!',
  CHECK_POLICY = OFF,
  CHECK_EXPIRATION = OFF;

-- Grant access to the database
USE EBR_Template;
CREATE USER traksys_app FOR LOGIN traksys_app;
ALTER ROLE db_datareader ADD MEMBER traksys_app;
ALTER ROLE db_datawriter ADD MEMBER traksys_app;
```

### Test the login from Windows (must work before Docker)

```powershell
sqlcmd -S localhost,1433 -U traksys_app -P "YourPassword99!" -Q "SELECT 1" -C
# Should return: 1
```

> ❌ Do NOT proceed to Docker until this works from Windows.

---

## Step 3 — Project `.env` File

Create a `.env` file in your project root. 

> ⚠️ Critical rules:
> - **No quotes** around `MSSQL_CONNECTION_STRING`
> - Use `host.docker.internal` not `localhost` for SQL Server
> - Use `Trusted_Connection=no` with `UID`/`PWD` — Windows Auth does not work from Docker

```env
# Database — NO quotes, host.docker.internal, Trusted_Connection=no
MSSQL_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=host.docker.internal,1433;Database=EBR_Template;Trusted_Connection=no;UID=traksys_app;PWD=YourPassword99!;TrustServerCertificate=yes

MSSQL_USER=traksys_app
MSSQL_PASSWORD=YourPassword99!

# App
CLAUDE_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
USE_UV=0

# Security
READ_ONLY=true
ENABLE_WRITES=false

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Timeouts & Limits
MSSQL_CONNECTION_TIMEOUT=5
MSSQL_QUERY_TIMEOUT=30
MAX_ROWS=1000
MAX_QUERY_LENGTH=8000

# Transport
SERVER_TRANSPORT=stdio
HTTP_BIND_HOST=0.0.0.0
HTTP_BIND_PORT=8000

# OpenWebUI
WEBUI_SECRET_KEY=your-secret-key-here

# Langfuse
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=http://langfuse-langfuse-web-1:3000
ENABLE_TRACING=true
```

---

## Step 4 — Docker Compose

Your `docker-compose.yml` needs to join the `langfuse_default` external network so containers can talk to Langfuse by container name.

```yaml
services:

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    ports:
      - "3001:8080"
    environment:
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
    volumes:
      - open-webui-data:/app/backend/data
    networks:
      - langfuse_default
    restart: unless-stopped

  pipelines:
    image: ghcr.io/open-webui/pipelines:main
    container_name: pipelines
    ports:
      - "9099:9099"
    environment:
      - PIPELINES_API_KEY=0p3n-w3bu!
    volumes:
      - pipelines-data:/app/pipelines
    networks:
      - langfuse_default
    restart: unless-stopped

  traksys-mcp:
    build: .
    container_name: traksys-mcp
    ports:
      - "8000:8000"
    env_file:
      - .env
    networks:
      - langfuse_default
    restart: unless-stopped

volumes:
  open-webui-data:
  pipelines-data:

networks:
  langfuse_default:
    external: true
```

---

## Step 5 — Dockerfile

```dockerfile
FROM python:3.11-slim

# Install Microsoft ODBC Driver 17 for SQL Server
RUN apt-get update && apt-get install -y curl gnupg2 apt-transport-https && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev && \
    apt-get clean

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

# Install package (src layout — this registers traksys_mcp as a module)
RUN pip install -e .
RUN pip install langfuse mcpo

CMD ["mcpo", "--port", "8000", "--", "python", "-m", "traksys_mcp"]
```

> ⚠️ The `pip install -e .` is required for src layout projects. Without it you get `ModuleNotFoundError: No module named 'traksys_mcp'`.

---

## Step 6 — Start the Stack

```powershell
# Build and start
docker compose up -d --build

# Verify all containers are running
docker ps

# Check MCP server logs — should end with "Application startup complete"
docker compose logs --tail=30 traksys-mcp
```

**Healthy MCP server log looks like:**
```
✓ Tracing service ready (enabled=True)
Checking database connection...
Starting MCP server with STDIO transport
Server is ready and waiting for requests...
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

### Troubleshooting: container has wrong connection string

```powershell
# Verify what the container actually has
docker exec traksys-mcp env | findstr MSSQL_CONNECTION_STRING

# If it still shows old values, force recreate
docker compose up -d --force-recreate traksys-mcp
```

---

## Step 7 — OpenWebUI Configuration

Go to **http://localhost:3001** → Admin Panel (top right) → Settings.

### 7.1 Add Pipelines connection

**Settings → Connections**

The Pipelines endpoint should already show `http://pipelines:9099`. If not, add it via the **+** button next to OpenAI API with key `0p3n-w3bu!`.

### 7.2 Install Langfuse Pipeline

**Settings → Pipelines**

In the "Install from Github URL" box paste:
```
https://raw.githubusercontent.com/open-webui/pipelines/main/examples/filters/langfuse_v3_filter_pipeline.py
```

Click the download ⬇️ button. The pipeline will install and show valves below. Fill in:

| Valve | Value |
|---|---|
| Secret Key | `sk-lf-...` (your Langfuse secret key) |
| Public Key | `pk-lf-...` (your Langfuse public key) |
| Host | `http://langfuse-langfuse-web-1:3000` |

Click **Save**.

> ⚠️ Use the internal Docker container name `langfuse-langfuse-web-1:3000`, NOT `localhost:3000`. Containers cannot reach `localhost` on the host machine.

### 7.3 Add MCP Tool Server

**Settings → External Tools**

Click **+** and enter:
```
http://traksys-mcp:8000
```

No API key needed. Save. You should see "Traksys Management" appear in the list.

### 7.4 Add Claude Models

**Settings → Connections → + (next to OpenAI API)**

- URL: `https://api.anthropic.com/v1`
- Auth: leave Bearer blank
- Headers (JSON format):
```json
{"x-api-key": "sk-ant-YOUR_KEY_HERE", "anthropic-version": "2023-06-01"}
```

Then manually add model IDs (Anthropic's `/v1/models` endpoint is not compatible):

Click the **+** next to "Add a model ID" and add each:
```
claude-haiku-4-5-20251001
claude-sonnet-4-5
claude-opus-4-5
```

Save.

### 7.5 Verify Anthropic API key

```powershell
$headers = @{
    "x-api-key" = "sk-ant-YOUR_KEY"
    "anthropic-version" = "2023-06-01"
    "content-type" = "application/json"
}
$body = '{"model":"claude-haiku-4-5-20251001","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
Invoke-RestMethod -Uri "https://api.anthropic.com/v1/messages" -Method POST -Headers $headers -Body $body
# Should return a response with content
```

---

## Step 8 — Test the Full Stack

1. Open **http://localhost:3001**
2. Start a New Chat
3. Select a Claude model from the model picker
4. Click the **🔧 tools icon** in the chat input bar to enable TrakSYS tools
5. Ask one of these test queries:

```
Show me all batches from the last 7 days
What is the status of the most recent batch?
How many batches were completed yesterday?
What are the parameters for the latest batch?
Give me a summary of batch activity for this month
```

6. Open **http://localhost:3000** (Langfuse) and check for new traces appearing under your project.

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `Login failed for user 'sa'. (18456)` | Wrong credentials or Windows Auth only mode | Restart SQL Server service as Admin after setting LoginMode=2 in registry |
| `ModuleNotFoundError: No module named 'traksys_mcp'` | Missing `pip install -e .` in Dockerfile | Add `pip install -e .` before installing other packages |
| Container has stale env vars | Docker cached old env | Run `docker compose up -d --force-recreate traksys-mcp` |
| `MSSQL_CONNECTION_STRING` ignored | Value has quotes in `.env` | Remove quotes — pyodbc receives them literally |
| OpenAI: Invalid bearer token (Anthropic) | Anthropic uses `x-api-key` not Bearer | Use Headers field with `{"x-api-key": "..."}` instead |
| Langfuse pipeline can't reach Langfuse | Using `localhost:3000` in valve config | Use `http://langfuse-langfuse-web-1:3000` (container name) |
| Tools not appearing in chat | Tools not enabled for conversation | Click 🔧 icon in chat input bar to toggle tools on |

---

## Network Reference

All services that need to talk to each other must be on the same Docker network (`langfuse_default`).

```
open-webui  ──→  pipelines:9099         (pipeline filter)
open-webui  ──→  traksys-mcp:8000       (MCP tools via OpenAPI)
pipelines   ──→  langfuse-langfuse-web-1:3000   (send traces)
traksys-mcp ──→  langfuse-langfuse-web-1:3000   (send traces)
traksys-mcp ──→  host.docker.internal:1433       (SQL Server on Windows host)
```