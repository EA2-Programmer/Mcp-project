# TrakSYS MCP Server — Full Project Phase Map

## Project Goal
A full AI observability stack for manufacturing:
- User types a query in **OpenWebUI**
- An **LLM** (Claude or GPT) decides which **MCP tool** to call
- The MCP tool queries a **SQL Server** database (TrakSYS EBR_Template)
- Every layer — user query, LLM reasoning, tool call, DB query — is visible as a trace in **Langfuse**
- Tools are **self-documenting** and **explainable** — the system can explain its own methodology accurately, model-agnostic

---

## Stack
| Service | URL | Status |
|---|---|---|
| OpenWebUI | localhost:3001 | ✅ Running |
| Pipelines | localhost:9099 | ✅ Running |
| TrakSYS MCP | localhost:8000 | ✅ Running |
| Langfuse | localhost:3000 | ✅ Running |
| SQL Server | localhost:1433 (Windows host) | ✅ Running |

All containers on `langfuse_default` external network.

---

## PHASE 0 — FOUNDATION
**Status: ✅ COMPLETE**

- [x] Docker stack running: OpenWebUI, Pipelines, traksys-mcp, Langfuse (web + worker + postgres + redis + minio + clickhouse)
- [x] SQL Server mixed authentication mode enabled (LoginMode=2 via registry, restarted as Admin)
- [x] `traksys_app` SQL login created with db_datareader + db_datawriter on EBR_Template
- [x] `.env` configured correctly — no quotes, `host.docker.internal`, `traksys_app` credentials
- [x] `pip install -e .` in Dockerfile — package registered via src layout
- [x] `mcpo` wrapping MCP server so OpenWebUI can call it as OpenAPI endpoint
- [x] Anthropic API key configured in OpenWebUI (via Headers field, not Bearer)
- [x] Langfuse pipeline installed from GitHub URL, Host set to `http://langfuse-langfuse-web-1:3000`
- [x] MCP tools registered in OpenWebUI at `http://traksys-mcp:8000`
- [x] Claude models added: claude-haiku-4-5-20251001, claude-sonnet-4-5, claude-opus-4-5

---

## PHASE A — BATCH DOMAIN TOOLS
**Status: ✅ COMPLETE**

Five tools fully built, tested, and returning real data from EBR_Template:

- [x] `get_batches` — query batches with time intelligence and smart fallback
- [x] `get_batch_parameters` — process parameter readings with deviation detection
- [x] `get_batch_materials` — actual material consumption via tBatch → tJob → tMaterialUseActual
- [x] `get_batch_details` — full drill-down: steps, operator remarks (_DBR), compliance tasks (tTask)
- [x] `get_batch_quality_analysis` — three-signal quality assessment (parameter deviations + operator remarks + incomplete tasks)

All tools have:
- [x] Langfuse tracing (trace_tool context manager, child DB spans, set_output, record_error)
- [x] ToolResponse structured responses (success / partial / no_data / error)
- [x] Time resolution service (natural language time windows, automatic fallback)
- [x] Tool descriptions with use-case examples

Verified working queries: batch 462 (materials, quality), batch 457, batch 461, 464, 466, 468, 473

---

## PHASE B — OBSERVABILITY
**Status: ✅ COMPLETE**

- [x] Langfuse v3 TracingService in MCP server — fire-and-forget, non-blocking
- [x] MCP tool calls → named traces in Langfuse (`tools/call get_batch_details` etc.)
- [x] DB child spans inside each tool trace
- [x] OpenWebUI/LLM conversations → traces via Langfuse filter pipeline (inlet/outlet)
- [x] Token costs tracked in Langfuse dashboard
- [x] Same chat session = one trace; new chat = new trace

**Known bug — PENDING fix:**
- [ ] `set_output()` in langfuse_tracing.py sends column names instead of actual row values in `sample_data` field. The data dict needs to serialize actual row contents, not just column metadata.

---

## PHASE C — EXPLAINABILITY
**Status: 🔄 IN PROGRESS**

This phase implements two complementary explainability mechanisms so the system can accurately explain its own methodology regardless of which LLM is connected.

### C1 — Meta Tool: `get_tool_explanation`
**Status: ✅ Built, needs deploying**

File created: `src/traksys_mcp/tools/meta.py`

- [x] `TOOL_EXPLANATIONS` dict — single source of truth for methodology of all tools
- [x] `get_tool_explanation(tool_name)` MCP tool — returns exact methodology as a tool response (not a docstring)
- [x] Supports `tool_name='all'` to list all available tools and their purposes
- [x] Covers: get_batches, get_batch_parameters, get_batch_materials, get_batch_details, get_batch_quality_analysis, get_equipment_state
- [x] Langfuse tracing included

**Still to do:**
- [ ] Copy `meta.py` to `src/traksys_mcp/tools/meta.py` in the project
- [ ] Register `MetaTools` in `server.py`:
  ```python
  from src.traksys_mcp.tools.meta import MetaTools
  meta_tools = MetaTools(mcp=self.mcp, tracing=self.tracing)
  meta_tools.register()
  ```
- [ ] Rebuild Docker: `docker compose up -d --build --force-recreate traksys-mcp`
- [ ] Test: ask "How does the batch quality analysis work?" — Claude should call `get_tool_explanation` and report the exact three-signal methodology, not hallucinate
- [ ] Verify in Langfuse: `get_tool_explanation` trace appears confirming tool was called

### C2 — Self-Documenting Tool Responses
**Status: ⬜ NOT STARTED**

Every tool response should include a `methodology` block so the LLM has accurate context inline with the data — without needing to call a separate explanation tool.

This is model-agnostic: any LLM (Claude, GPT, Llama) receives the methodology and can reference it accurately.

The `methodology` block should be **business-readable**, not technical. No SQL queries, no table names. Example for `get_batch_quality_analysis`:

```json
{
  "data": { "...actual results..." },
  "methodology": {
    "approach": "Three-signal quality assessment",
    "signals_checked": [
      "Parameter readings compared against allowed min/max limits",
      "Operator notes scanned for problem keywords",
      "Mandatory compliance tasks checked for completion"
    ],
    "verdict_logic": "Batch flagged if any single signal triggers",
    "coverage": "8 parameters checked, 9 operator remarks scanned, 2 tasks verified"
  }
}
```

**To do for each tool:**
- [ ] `get_batch_quality_analysis` — add methodology block (highest priority, most complex tool)
- [ ] `get_batch_parameters` — add methodology block (deviation detection logic)
- [ ] `get_batch_details` — add methodology block (four sections explained)
- [ ] `get_batch_materials` — add methodology block (tBatch → tJob → tMaterialUseActual chain)
- [ ] `get_batches` — add methodology block (time resolution + fallback logic)
- [ ] All Phase C/D new tools — build with methodology block from the start

**Implementation note:** The `methodology.coverage` field should be dynamically populated — actual counts from the query (how many parameters were checked, how many remarks were scanned etc.), not hardcoded values.

### C3 — Intent Logging in Langfuse
**Status: ⬜ NOT STARTED**

Currently Langfuse shows *what tool was called* but not *why the LLM chose that tool*. Intent logging adds a Layer 1.5 between LLM reasoning and tool execution.

The goal is for Langfuse to show:
```
Trace: get_batch_quality_analysis
├─ Intent: User asked "Were there quality issues with batch 462?"
├─ Reasoning: "quality issues" → multi-signal quality analysis tool
├─ Entities extracted: batch_id=462
├─ Input: {batch_id: 462}
├─ Output: {deviations: [...], remarks: [...], tasks: [...]}
```

**To do:**
- [ ] Investigate how to capture the original user query in the MCP tool context (OpenWebUI may need to pass it as a metadata header or parameter)
- [ ] Add `log_intent(span, original_query, extracted_entities)` method to `TracingService`
- [ ] Call `log_intent` at the start of each tool handler before the service call
- [ ] Verify intent appears as a span attribute in Langfuse

### C4 — System Prompt Enhancement
**Status: ⬜ NOT STARTED**

One-line addition to OpenWebUI system prompt to tell the LLM to reference methodology when answering:

```
When explaining results, always reference the methodology field in the tool response. 
For example: "Using the three-signal quality assessment approach, batch 462 was flagged because..."
```

**To do:**
- [ ] Add system prompt in OpenWebUI Settings → Models (or per-model system prompt)
- [ ] Test: ask about batch 462 quality — response should explicitly mention "three-signal approach" or equivalent
- [ ] Verify this works consistently across Claude Sonnet and GPT-4

---

## PHASE D — NEW TOOLS (PERFORMANCE & EQUIPMENT)
**Status: ⬜ NOT STARTED**

### D1 — Task Domain Tools
Real data confirmed: 310 rows in tTask.

- [ ] `get_batch_tasks` — retrieve all tasks for a batch with completion status, operator, timestamps
- [ ] `analyze_task_compliance` — compliance rate across batches/time periods, identify which task types fail most
- [ ] Build with self-documenting responses from the start (Phase C2 pattern)

### D2 — Trend Analysis Tools
- [ ] `analyze_batch_trend` — parameter trends over time (e.g. is Temperature drifting batch over batch?)
- [ ] `compare_periods` — compare quality/performance metrics between two time periods

### D3 — Equipment / OEE Tools
**Note: Real OEE tables (tOeeInterval, tOeeCalculation) — data status unknown. Check first:**
```sql
SELECT COUNT(*) FROM tOeeInterval;
SELECT COUNT(*) FROM tOeeCalculation;
```

- [ ] `get_equipment_state` — current status, availability, live tags (already documented in meta.py)
- [ ] If OEE tables are empty: inject mock data for E1 line, build `get_oee_metrics` tool against mock data
- [ ] `get_machine_downtime` — fault events and downtime periods (requires tEvents data — currently empty, needs mock injection)

### D4 — Multi-Line Comparison
**Note: Only E1 has real data. E2/E3 need mock data injection.**

- [ ] Inject mock batch + parameter data for lines E2 and E3 into EBR_Template
- [ ] `compare_lines` — side-by-side OEE, quality, throughput comparison across E1/E2/E3

### D5 — Shift Analysis
**Note: tShift, tShiftHistory, tTeam tables are currently empty.**

- [ ] Inject mock shift data (08:00-16:00, 16:00-22:00, 22:00-08:00 schedule)
- [ ] `get_shift_performance` — quality and throughput by shift, identify which shift has most deviations

---

## PHASE E — DATA QUALITY & MOCK DATA
**Status: ⬜ NOT STARTED**

Several gaps in the real database require mock data to demonstrate full capabilities:

- [ ] **OEE data**: Inject realistic data into tOeeInterval and tOeeCalculation for line E1
- [ ] **Machine downtime events**: Inject fault events into tEvents with fault codes, durations, affected line
- [ ] **E2/E3 line data**: Inject batches, parameters, materials for two additional production lines
- [ ] **Shift data**: Inject shift schedules into tShift/tShiftHistory/tTeam
- [ ] **Material names**: Currently generic (Material 1, M1 etc.) — either rename or document as demo limitation
- [ ] **ActualBatchSize**: Currently 0 for all batches — investigate if this is a TrakSYS config issue or data gap

---

## PHASE F — HARDENING & PRODUCTION READINESS
**Status: ⬜ NOT STARTED**

- [ ] Fix `set_output()` bug in langfuse_tracing.py (sample_data shows column names not row values) — **this was pending from Phase B**
- [ ] Add request-level error handling — if SQL Server is unreachable, tools should return graceful degradation responses not crash
- [ ] Add connection pooling in database.py — currently opens/closes connection per query
- [ ] Rate limiting on MCP tools — prevent runaway queries
- [ ] Structured logging (JSON format) for all tool calls
- [ ] Health check endpoint on traksys-mcp container
- [ ] Secrets management — move API keys and DB credentials out of .env into Docker secrets or vault
- [ ] Update SETUP_GUIDE.md to reflect all Phase C/D additions

---

## Key Architectural Decisions (Already Made)

| Decision | Choice | Reason |
|---|---|---|
| Explainability location | MCP server (not LLM prompts) | Model-agnostic, survives LLM swaps |
| Methodology delivery | Tool response (not docstring) | LLMs report tool responses accurately, remix docstrings |
| Tracing | Fire-and-forget | Langfuse unavailability should never block tool execution |
| SQL Auth | traksys_app login (not sa) | Least privilege, dedicated app user |
| Container networking | langfuse_default external network | All containers can reach each other by name |
| Package layout | src/ layout, pip install -e . | Clean imports, works inside Docker |

---

## Current .env (Working)
```
MSSQL_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=host.docker.internal,1433;Database=EBR_Template;Trusted_Connection=no;UID=traksys_app;PWD=TrakSYS99!;TrustServerCertificate=yes
MSSQL_USER=traksys_app
MSSQL_PASSWORD=TrakSYS99!
CLAUDE_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
WEBUI_SECRET_KEY=cQDOOOKH1QRqYqRt
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=http://langfuse-langfuse-web-1:3000
ENABLE_TRACING=true
```

## Rebuild Command (after any code change)
```powershell
docker compose up -d --build --force-recreate traksys-mcp
```

## Verify file in container (PowerShell)
```powershell
docker exec traksys-mcp cat /app/src/traksys_mcp/tools/meta.py | Select-String "get_tool_explanation"
```