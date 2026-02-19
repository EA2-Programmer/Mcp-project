# TrakSYS MCP Server

Manufacturing Analytics Platform

## Prerequisites

- Python 3.9+
- Anthropic API Key

## Setup test

### Step 1: Pull the project repository

1. Clone repository

### Step 2: Configure the environment variables

2. Create or edit the `.env` file in the project root and verify that the following variables are set correctly:

```
ANTHROPIC_API_KEY=""  # Enter your Anthropic API secret key
```

### Step 3: Install dependencies

#### Option 1: Setup with uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

3. Install uv, if not already installed:

```bash
pip install uv
```

4. Create and activate a virtual environment:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

5. Install dependencies:

```bash
uv pip install -e .
```

6. Run the project

```bash
uv run python src/server.py
```


## Features

- 8 composable entity-based tools
- 2 guided investigation prompts
- Read-only secure access
- OpenWebUI integration ready

## Documentation
# this is the .env file
```

# Database connection
#MSSQL_CONNECTION_STRING="Driver={ODBC Driver 17 for SQL Server};Server=localhost,1433;Database=EBR_Template;Trusted_Connection=yes"

MSSQL_CONNECTION_STRING="Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=EBR_Template;Trusted_Connection=yes;TrustServerCertificate=yes"


CLAUDE_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=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
USE_UV=0

# Security
READ_ONLY=true
ENABLE_WRITES=false

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Timeouts
MSSQL_CONNECTION_TIMEOUT=5
MSSQL_QUERY_TIMEOUT=30

# Limits
MAX_ROWS=1000
MAX_QUERY_LENGTH=8000

SERVER_TRANSPORT=stdio
HTTP_BIND_HOST=0.0.0.0
HTTP_BIND_PORT=8080
````

## Demo

