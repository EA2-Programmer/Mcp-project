# Building a production-grade AI assistant on TrakSYS MES with MCP

**Your MCP server likely has critical gaps in validation, error handling, and tool design; your Langfuse setup is almost certainly using less than 20% of its capabilities; and your architecture needs a structured evaluation pipeline before it can be considered production-ready.** This report provides a complete technical blueprint across all five areas you identified — MCP server robustness, Langfuse utilization, architecture optimization, evaluation strategy, and industry references — with specific code patterns and implementation recommendations for a TrakSYS MES use case.

---

## 1. What makes an MCP server production-grade

The Model Context Protocol specification (stable version 2025-11-25) defines three core primitives: **tools** (LLM-invoked functions), **resources** (URI-addressable data), and **prompts** (reusable templates). The Python SDK's `FastMCP` class provides decorator-based registration for all three. The critical difference between a student POC and a production server lies in ten specific patterns.

### Validation, error handling, and safety patterns

Every tool parameter should be validated through Pydantic models with custom validators. For manufacturing data, this means enforcing maximum time windows (30 days), defaulting to shift-aligned boundaries, and restricting identifiers to safe character sets:

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timedelta

class TimeRangeParams(BaseModel):
    start_time: datetime = Field(description="Start of time range (ISO 8601)")
    end_time: datetime = Field(description="End of time range (ISO 8601)")

    @field_validator('end_time')
    @classmethod
    def validate_time_range(cls, v, info):
        start = info.data.get('start_time')
        if start and (v - start) > timedelta(days=30):
            raise ValueError("Time range cannot exceed 30 days. Use pagination.")
        return v

class ProductionQueryParams(TimeRangeParams):
    line_id: str = Field(min_length=1, max_length=50, pattern=r'^[A-Za-z0-9_-]+$')
    limit: int = Field(default=1000, ge=1, le=10000)
```

Error handling must serve the LLM, not just the developer. Every error response should contain **(1)** what happened, **(2)** why, and **(3)** what valid inputs look like — this enables the LLM to self-correct on retry. Wrap every tool in structured exception handling with `asyncio.wait_for()` timeouts (30 seconds for queries, 5 seconds for connections). SQL injection prevention is non-negotiable: **always use parameterized queries, never accept raw SQL from the LLM**, and use a read-only database user. A 2025 security audit found that 43% of popular MCP server implementations had command injection vulnerabilities.

### Connection pooling and lifecycle management

Use the `FastMCP` lifespan pattern to manage database connection pools across the server's lifecycle:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    pool = await aioodbc.create_pool(
        dsn='DRIVER={ODBC Driver 18 for SQL Server};SERVER=traksys-db;DATABASE=TrakSYS',
        minsize=5, maxsize=20, pool_recycle=3600
    )
    try:
        yield AppContext(db_pool=pool)
    finally:
        pool.close()
        await pool.wait_closed()

mcp = FastMCP("TrakSYS MES", lifespan=app_lifespan)
```

### MES-specific tool design

The most important design principle: **don't map tools 1:1 to database tables or API endpoints**. Design tools around "agent stories" — complete units of analytical work. Block's engineering team reduced their entire Square API surface to 3 conceptual tools. Benchmarks show tool selection accuracy degrades logarithmically as tool count increases.

For TrakSYS, a production MCP server needs **8–12 well-designed tools** across these categories:

- **`get_oee_summary`** — OEE breakdown (A×P×Q) with configurable granularity (hourly/shift/daily)
- **`get_downtime_analysis`** — Ranked downtime events with reason codes and cumulative impact
- **`get_production_counts`** — Good/reject/total counts with product filtering
- **`get_equipment_status`** — Real-time state of all assets or a specific line
- **`get_quality_metrics`** — First-pass yield, reject rates, optional SPC data with UCL/LCL
- **`get_alarm_history`** — Severity-filtered alarm events with acknowledgment status
- **`track_batch`** — Genealogy, materials consumed, process steps, quality results
- **`get_shift_summary`** — Composite tool combining OEE + production + downtime + quality for shift handoffs

Each tool's docstring is its user manual for the LLM. Specify **when** to use it, **how** to format arguments, and **what** to expect back. Complement these tools with **resources** (line configuration, product catalog, reason code hierarchy, shift schedule definitions) and **prompts** (shift handoff analysis, root cause investigation, daily production review).

### The 10 most common POC gaps

The gaps that most commonly distinguish a student implementation from a production one: **(1)** No time-window safeguards — LLMs can request unbounded queries scanning millions of rows. **(2)** Missing connection pooling — creating a new DB connection per request devastates async performance. **(3)** Silent failures returning empty responses instead of descriptive errors with recovery hints. **(4)** 1:1 REST-to-tool mapping inflating tool count. **(5)** stdout pollution on stdio transport corrupting JSON-RPC. **(6)** No pagination for large result sets. **(7)** No shift-awareness — queries should default to shift-aligned boundaries, not arbitrary UTC ranges. **(8)** Returning raw database column names instead of human-readable labels. **(9)** No rate limiting against agentic loops issuing hundreds of rapid tool calls. **(10)** No authentication on remote HTTP transports — OAuth 2.1 is mandatory per the MCP specification.

---

## 2. Langfuse: from basic logging to full utilization

Most teams use less than 20% of Langfuse's capabilities. A basic setup captures flat traces with LLM input/output. Full utilization transforms Langfuse into a complete development and evaluation platform with five distinct product surfaces.

### Structured observation hierarchy for MCP agents

Langfuse's data model supports **sessions → traces → observations** with typed observation nodes: `generation` (LLM calls), `tool` (MCP invocations), `span` (duration blocks), `retriever`, `agent`, and `evaluator`. For an MCP agent, every tool call should be a separate `tool`-type observation with captured input parameters and output data:

```python
from langfuse import get_client, propagate_attributes

langfuse = get_client()

with langfuse.start_as_current_observation(
    as_type="span", name="agent-request",
    input={"user_query": "What was OEE on Line 2 yesterday?"}
) as root:
    with propagate_attributes(user_id="operator_42", session_id="shift_handoff_001"):
        with langfuse.start_as_current_observation(
            as_type="generation", name="planning-llm", model="gpt-4o"
        ) as gen:
            gen.update(output="I'll query OEE metrics",
                      usage_details={"input": 150, "output": 30})

        with langfuse.start_as_current_observation(
            as_type="tool", name="mcp-get-oee-summary",
            input={"line_id": "LINE-02", "start": "2026-03-12", "end": "2026-03-12"}
        ) as tool:
            tool.update(output={"oee": 82.5, "availability": 91.2})
```

Langfuse has **dedicated MCP tracing support** that propagates OpenTelemetry context (W3C Trace Context format) through MCP's `_meta` field, creating unified traces that span client and server boundaries. A complete implementation example exists at `github.com/langfuse/langfuse-examples/tree/main/applications/mcp-tracing`.

### The evaluation features you're probably not using

Langfuse's most underutilized capabilities form a complete evaluation pipeline. **LLM-as-a-Judge evaluators** run automatically on production traces — built-in templates cover hallucination, helpfulness, relevance, toxicity, and correctness, with support for custom evaluation prompts. **Annotation queues** enable structured human review workflows with task assignment. **Datasets** store input/expected-output pairs, populated from production traces or created manually. **Experiments** run your application against datasets, score outputs automatically, and provide side-by-side comparison views.

The full development loop looks like this: production traces flow in → problematic traces get flagged → they're added to datasets with expert-annotated expected outputs → prompt/model changes are tested against these datasets → LLM-as-judge scores experiments → CI/CD gates block regressions.

### Prompt management closes the loop

Langfuse's prompt management stores all prompts with version control, labels (`production`, `staging`), variables, and per-version performance metrics. This means you can track exactly which prompt version produced which quality scores, run A/B tests between versions, and protect production prompts from unauthorized changes. The SDK caches prompts client-side with configurable TTL. Moving prompts from hardcoded strings to Langfuse-managed templates is one of the highest-leverage changes you can make.

### Basic vs full utilization at a glance

A basic setup logs flat traces and captures LLM input/output. A fully-utilized setup adds: nested typed observation hierarchy, session tracking across conversation turns, user tracking, rich metadata/tags for filtering, environment separation, token usage and cost tracking, LLM-as-judge evaluators on production traces, annotation queues for human review, user feedback collection, datasets built from production failures, experiment pipelines for prompt/model changes, prompt management with version control and labels, custom dashboards monitoring quality/cost/latency, and spend alerts.

---

## 3. Architecture: from OpenWebUI to SQL Server

### How OpenWebUI connects to MCP

Open WebUI **natively supports MCP** starting in v0.6.31 via Streamable HTTP transport. Configuration is straightforward: Admin Settings → External Tools → Add Server → set type to "MCP (Streamable HTTP)." For MCP servers using stdio transport (the most common development pattern), Open WebUI provides **MCPO** (`github.com/open-webui/mcpo`), an open-source proxy that wraps any stdio-based MCP server as an OpenAPI-compatible HTTP endpoint.

**Recommended path for your project**: Build your TrakSYS MCP server using FastMCP, deploy it as a Streamable HTTP server, and connect directly to OpenWebUI. If you're using stdio during development, use MCPO as a bridge. The end-to-end data flow is:

```
User (Browser) → OpenWebUI → LLM (Ollama/API) → MCP Server → SQL Server (TrakSYS)
                                                      ↕
                                                  Langfuse (tracing)
```

### Function calling beats ReAct for structured MES tools

For well-defined tools with typed parameters (which is exactly what MES queries are), **function calling** outperforms ReAct. Modern LLMs have been specifically trained on function-calling data structures. The MCP tool definitions map naturally to function-calling schemas. For complex multi-step queries, layer reasoning on top: the LLM reasons about which tools to call in sequence, but each individual invocation uses structured function calling.

### The hybrid text-to-SQL approach

Use **parameterized query templates for ~80% of queries** (OEE, downtime, production counts — these are well-defined and high-frequency) and **text-to-SQL for ~20%** (ad-hoc analytical queries). This hybrid approach is critical because GPT-4o drops from **86.6% accuracy** on simple SQL benchmarks to just **10.1%** on enterprise-grade ones (SPIDER2 benchmark). Parameterized templates guarantee correctness for common queries while preserving flexibility.

For the text-to-SQL tool, implement safety guardrails: read-only database user, SQL parsing to reject DDL/DML, query timeouts, row limits, explicit SQL dialect specification ("Generate T-SQL for SQL Server"), and a validation-reprompting loop where SQL errors are passed back to the LLM for correction.

### Context window management for large MES results

JetBrains Research (December 2025) found that LLM summarization causes agents to run ~15% longer than observation masking. The recommended approach is **hybrid**: replace old tool results with compact placeholders by default, and use LLM summarization only at logical breakpoints. Design MCP tools to return pre-aggregated summaries by default (e.g., "Top 5 downtime reasons with cumulative percentage") with a `detail` parameter for raw data. Always paginate large result sets with cursors.

### System prompt engineering for manufacturing

Your system prompt should include: facility-specific domain knowledge (OEE formulas and benchmarks, shift schedule definitions, timezone handling), explicit guidelines for when to use each tool, manufacturing terminology mappings, common ambiguity resolution patterns ("How's the line doing?" → clarify which line, which metric, which timeframe), and 3–5 few-shot examples of user queries mapped to expected tool call sequences. The "Chat with MES" paper recommends an **Operational Procedure Document** that maps natural language patterns to specific system operations.

---

## 4. Evaluation strategy: what to test and how

### Three-layer metric framework

Evaluation for tool-calling agents requires metrics at three distinct layers. **Reasoning metrics** assess plan quality and adherence — did the agent form a logical plan and follow it? **Action metrics** assess tool selection accuracy, parameter extraction correctness, and tool call ordering. **End-to-end metrics** assess task completion, answer correctness, hallucination rate, and latency. Anthropic's evaluation guide (January 2026) emphasizes that agent evaluations require **multiple trials per task** due to non-determinism, and evaluation of both the transcript (reasoning trace) and the outcome (final answer).

The specific metrics that matter most for your manufacturing agent:

- **Tool Call F1**: Precision and recall of tools called vs. expected (promptfoo's `tool-call-f1` assertion)
- **Parameter Extraction Accuracy**: Did time windows, line IDs, and product codes match expectations?
- **Numerical Accuracy**: OEE values within ±0.5%, production counts exact match
- **Time Window Correctness**: Did "last shift" resolve to the correct UTC boundaries?
- **Task Completion Rate**: Binary or graded measure of whether the user's question was answered
- **Hallucination Rate**: Did the agent fabricate data not present in tool outputs?

### Building a 200-case ground truth test set

Structure test cases with five tiers: **(1)** Unit tests for individual MCP tools in isolation, **(2)** integration tests for multi-tool workflows, **(3)** end-to-end conversation tests with full ground truth, **(4)** edge cases (ambiguous queries, out-of-scope questions, adversarial inputs, temporal ambiguity), and **(5)** regression tests that capture previously fixed bugs.

For manufacturing coverage, aim for **~200 test cases** stratified as: 40 OEE queries, 30 downtime analysis, 25 production counts, 25 quality metrics, 20 multi-step reasoning, 20 edge cases, 15 adversarial/security, 15 temporal reasoning, 10 unit handling. Each test case should include the query, expected tool calls with parameters, expected answer with tolerance, and grading criteria.

Handle time-dependent answers by: parameterizing dates (resolve "yesterday" at test time against a fixed reference), using a deterministic mock MES database with known data for known time windows, and applying tolerance-based assertions rather than exact matches.

### Recommended evaluation tool stack

The most effective combination is **promptfoo + DeepEval + Langfuse**. Use **promptfoo** for declarative YAML-based regression tests with `tool-call-f1` assertions, CI/CD integration, and MCP security testing (it has native MCP provider support). Use **DeepEval** for component-level evaluation with `ToolCorrectnessMetric`, `TaskCompletionMetric`, and custom `GEval` criteria. Use **Langfuse** for production trace collection, dataset management, LLM-as-judge evaluators, and experiment comparison.

Set CI/CD gate thresholds at: tool selection accuracy ≥95%, parameter extraction ≥90%, numerical correctness ≥90%, task completion ≥90%, hallucination rate ≤5%, and P95 latency <10 seconds. Run the full regression suite on every PR that touches prompts, tools, or agent code.

### LLM-as-judge calibration

For the LLM judge, use a stronger model than your agent model, structured rubrics with additive scoring (break judgment into atomic criteria, award points independently), chain-of-thought prompting before the final score, and reference-based scoring with the gold standard answer as anchor. **Calibrate against 50+ human-annotated examples** and target >80% judge-human agreement before trusting automated evaluations.

---

## 5. Industry references and benchmark projects

### Most relevant reference implementations

The **AWS industrial-data-store-simulation-chatbot** (`github.com/aws-samples/industrial-data-store-simulation-chatbot`) is the single most relevant reference for your project — a complete simulated MES on SQLite with an AI chatbot powered by Amazon Bedrock, featuring text-to-SQL with tool use, simulated production patterns (bottlenecks, maintenance cycles, quality issues), and a Jupyter notebook demonstrating the query patterns.

The **"Chat with MES" (CWM)** paper published in the Journal of Manufacturing Systems (2025) provides academic validation: an LLM agent system integrating into a garment manufacturing MES with a 16-table relational database, achieving **80% execution accuracy** using request rewriting and multi-step dynamic operations generation.

The **poly-mcp/IoT-Edge-MCP-Server** (`github.com/poly-mcp/IoT-Edge-MCP-Server`) is the most complete open-source industrial MCP implementation, unifying MQTT sensors, Modbus devices, and industrial equipment into a single AI-orchestrable API with real-time monitoring, alarms, and time-series storage.

### TrakSYS-specific context

Parsec released **TrakSYS IQ** in TrakSYS 14 (February 2026), a conversational AI built with Microsoft Azure AI Foundry for natural language queries against manufacturing data. Your custom MCP-based approach parallels this commercial offering but gives you more control over model selection, tool definitions, and prompt engineering. TrakSYS's open SQL Server database and RESTful APIs make it well-suited for MCP server wrapping.

### Additional references worth studying

- **RichardHan/mssql_mcp_server** — Direct MSSQL MCP server, directly applicable to TrakSYS's SQL Server backend
- **Litmus MCP Server** — Production industrial IoT MCP server listed in the official MCP registry
- **AWS IoT SiteWise MCP Server** — Enterprise AWS-backed MCP for industrial asset management
- **MDPI paper on domain-specific manufacturing analytics** — RAG architecture with FastAPI + Ollama for MES text-to-SQL
- **Google Cloud text-to-SQL techniques** — Best practices for schema context injection, table retrieval, and validation-reprompting patterns
- **Contextual AI open-source text-to-SQL** — Best local system on the BIRD benchmark using M-Schema format

---

## Conclusion: a phased implementation roadmap

The gap between your current POC and a production-grade system is best closed in three phases. **Phase 1 (weeks 1–3)**: Harden the MCP server with Pydantic validation, time-window safeguards, parameterized queries, connection pooling, and structured error handling. Deploy via Streamable HTTP to OpenWebUI. Configure Langfuse with nested observation hierarchy, typed MCP tool spans, and session tracking.

**Phase 2 (weeks 4–6)**: Build the evaluation pipeline — create 50 initial test cases in promptfoo, set up Langfuse datasets and LLM-as-judge evaluators, implement the CI/CD gate. Move prompts into Langfuse prompt management. Add the hybrid text-to-SQL tool with safety guardrails. Implement context window management with server-side aggregation and pagination.

**Phase 3 (weeks 7–10)**: Expand the test set to 200 cases, calibrate the LLM judge against human annotations, run security red-teaming with promptfoo, build custom Langfuse dashboards for quality/cost/latency monitoring, and establish the continuous improvement loop where production failures feed back into the test dataset. The most impactful single investment is the evaluation pipeline — without it, every other improvement is guesswork.