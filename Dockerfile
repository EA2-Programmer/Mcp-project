# ── TrakSYS MCP Server ─────────────────────────────────────────────────────
# Builds the Python MCP server and wraps it with mcpo so OpenWebUI can reach
# it as a standard OpenAPI / HTTP endpoint.
#
# Base: python:3.11-slim  (matches pyproject.toml requires-python >=3.10)
# ODBC: Microsoft ODBC Driver 17 for SQL Server (required by pyodbc on Linux)
# ───────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System deps + Microsoft ODBC Driver 17 ─────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        unixodbc \
        unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] \
        https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Copy project files ──────────────────────────────────────────────────────
COPY requirements.txt pyproject.toml ./
COPY src/ ./src/

# ── Install dependencies + the package itself ───────────────────────────────
# pip install -e . reads pyproject.toml which has:
#   [tool.setuptools.packages.find] where = ["src"]
# This registers traksys_mcp on sys.path so `import traksys_mcp` works
# from anywhere — including when mcpo spawns it as a subprocess.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir langfuse mcpo \
    && pip install --no-cache-dir -e .

# ── Runtime ─────────────────────────────────────────────────────────────────
EXPOSE 8000

# Use `traksys_mcp` (not `src.traksys_mcp`) because pip install -e .
# registers the package at the top level via src/ layout.
CMD ["mcpo", "--port", "8000", "--", "python", "-m", "traksys_mcp"]