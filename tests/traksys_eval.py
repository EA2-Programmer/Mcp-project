"""
TrakSYS MCP — Langfuse Dataset Evaluation Script
=================================================
How it works:
  1. Reads your uploaded CSV from the Langfuse dataset
  2. Calls each MCP tool with the query
  3. Scores each result using keyword matching (fast, free)
  4. Posts every score back to Langfuse so it appears in the Dataset Run view
  5. Prints a final accuracy report

Run:
  pip install langfuse httpx python-dotenv
  python traksys_eval.py

Environment variables needed (same ones your MCP server uses):
  LANGFUSE_SECRET_KEY
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_BASE_URL        (e.g. https://cloud.langfuse.com)
  MCP_SERVER_URL           (e.g. http://localhost:8000)
"""

import os
import json
import time
import httpx
import logging
from dotenv import load_dotenv
from langfuse import get_client

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG — change these to match your setup
# ─────────────────────────────────────────────
DATASET_NAME   = "traksys-mcp-eval"   # Must match the name you used when uploading the CSV in Langfuse
EXPERIMENT_RUN = "run-v3-schema-fix"    # Name for this experiment run — change per run (e.g. run-v2-fix-oee)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

# ─────────────────────────────────────────────
# IMPORTANT: This script runs on your HOST machine (Windows laptop), NOT inside
# Docker. So Langfuse must be reached via localhost:3000, not the Docker-internal
# name "langfuse-web:3000" that your .env file uses for the containers.
# This line overrides whatever LANGFUSE_BASE_URL your .env file says.
# ─────────────────────────────────────────────
os.environ["LANGFUSE_BASE_URL"] = "http://localhost:3000"


# ─────────────────────────────────────────────
# STEP 1 — Initialize Langfuse client
# ─────────────────────────────────────────────
langfuse = get_client()


# ─────────────────────────────────────────────
# STEP 2 — Tool caller
# ─────────────────────────────────────────────

def _build_params(tool_name: str, query: str) -> dict:
    """
    Build the correct request body for each tool based on the real OpenAPI schema.

    CRITICAL: Most tools need {"params": {...}} wrapper.
    Flat tools (no wrapper): get_materials, get_products_using_materials,
                              calculate_oee, get_oee_downtime_events
    """
    import re

    def extract_int(text):
        m = re.search(r'\b(\d{3,})\b', text)
        return int(m.group(1)) if m else None

    def extract_date(text):
        m = re.search(r'\d{4}-\d{2}-\d{2}', text)
        return m.group(0) if m else None

    def extract_equipment(text):
        m = re.search(r'\b(E\d+)\b', text)
        return m.group(1) if m else None

    def extract_product(text):
        m = re.search(r'P\w+_FAC\w+_\w+', text)
        return m.group(0) if m else None

    def extract_material(text):
        m = re.search(r'\b(M\d+)\b', text)
        return m.group(1) if m else None

    if tool_name == "get_products":
        return {"params": {"limit": 100}}

    elif tool_name == "get_batches":
        p = {"limit": 50}
        m = re.search(r'\d{5}_\w+', query)
        if m:
            p["batch_name"] = m.group(0)
        if "abort" in query.lower():
            p["state"] = 5
        return {"params": p}

    elif tool_name == "get_batch_details":
        batch_id = extract_int(query)
        p = {}
        if batch_id:
            p["batch_id"] = batch_id
        return {"params": p}

    elif tool_name == "get_batch_parameters":
        batch_id = extract_int(query)
        p = {"limit": 100}
        if batch_id:
            p["batch_id"] = batch_id
        if "out-of-spec" in query.lower() or "deviation" in query.lower():
            p["deviation_only"] = True
        return {"params": p}

    elif tool_name == "get_batch_quality_analysis":
        batch_id = extract_int(query)
        p = {"limit": 100}
        if batch_id:
            p["batch_id"] = batch_id
        return {"params": p}

    elif tool_name == "get_batch_materials":
        batch_id = extract_int(query)
        p = {"limit": 100}
        if batch_id:
            p["batch_id"] = batch_id
        return {"params": p}

    elif tool_name == "get_batch_tasks":
        batch_id = extract_int(query)
        p = {"limit": 100}
        if batch_id:
            p["batch_id"] = batch_id
        if "incomplete" in query.lower():
            p["status_filter"] = "incomplete"
        return {"params": p}

    elif tool_name == "analyze_task_compliance":
        return {"params": {"limit": 100}}

    elif tool_name == "get_equipment_state":
        p = {"limit": 50}
        equipment = extract_equipment(query)
        if equipment:
            p["system_name"] = equipment
        return {"params": p}

    elif tool_name == "get_recipe":
        p = {"limit": 50}
        product = extract_product(query)
        batch_id = extract_int(query)
        if product:
            p["product_name"] = product
        elif batch_id:
            p["recipe_id"] = batch_id
        return {"params": p}

    elif tool_name == "get_materials":
        p = {"limit": 50}
        material = extract_material(query)
        if material:
            p["material_code"] = material
        return p

    elif tool_name == "get_products_using_materials":
        p = {"limit": 100}
        material = extract_material(query)
        if material:
            p["material_code"] = material
        return p

    elif tool_name == "calculate_oee":
        date = extract_date(query)
        equipment = extract_equipment(query)
        p = {"granularity": "daily", "breakdown": True}
        if date:
            p["start_date"] = date
            p["end_date"] = date
        if equipment:
            p["line"] = equipment
        return p

    elif tool_name == "get_oee_downtime_events":
        date = extract_date(query)
        equipment = extract_equipment(query)
        p = {"limit": 50}
        if date:
            p["start_date"] = date
            p["end_date"] = date
        if equipment:
            p["line"] = equipment
        return p

    return {}


def call_mcp_tool(tool_name: str, query: str) -> str:
    """
    Calls the TrakSYS MCP server tool with the correct parameters.
    URL format: http://localhost:8000/{tool_name}  (no /tools/ prefix — that's MCPO's format)
    """
    url = f"{MCP_SERVER_URL}/{tool_name}"        # ← fixed: no /tools/ prefix
    params = _build_params(tool_name, query)

    try:
        response = httpx.post(url, json=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        # MCPO wraps MCP responses in {"content": [{"type": "text", "text": "..."}]}
        if "content" in data and isinstance(data["content"], list):
            texts = [b.get("text", "") for b in data["content"] if b.get("type") == "text"]
            return " ".join(texts).strip()

        if "result" in data:
            return str(data["result"])

        return json.dumps(data)

    except httpx.HTTPStatusError as e:
        return f"HTTP_ERROR: {e.response.status_code} — {e.response.text[:300]}"
    except httpx.RequestError as e:
        return f"CONNECTION_ERROR: {e}"
    except Exception as e:
        return f"UNKNOWN_ERROR: {e}"


# ─────────────────────────────────────────────
# STEP 3 — Scoring functions
# ─────────────────────────────────────────────

def score_keyword_match(actual_output: str, expected_output: str) -> tuple[float, str]:
    """
    Extracts the key facts/numbers from expected_output and checks how many
    appear in actual_output. Returns a 0.0-1.0 score and a readable reason.

    This avoids the brittleness of exact-string matching — "26 batches" and
    "There are 26 batches in total" will both score correctly.
    """
    if not actual_output or actual_output.startswith(("HTTP_ERROR", "CONNECTION_ERROR", "UNKNOWN_ERROR")):
        return 0.0, f"Tool call failed: {actual_output}"

    # Pull out meaningful tokens from expected output (numbers + key nouns)
    import re
    # Extract numbers (e.g. "26", "98.2%", "3600")
    expected_numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', expected_output)
    # Extract capitalised IDs and names (e.g. "P00001_FAC1_0001", "M1", "Formulary")
    expected_tokens  = re.findall(r'\b[A-Z][A-Za-z0-9_]{2,}\b', expected_output)

    all_expected = expected_numbers + expected_tokens
    if not all_expected:
        # Fallback: simple substring check
        hit = expected_output.lower()[:40] in actual_output.lower()
        return (1.0 if hit else 0.0), ("Substring found" if hit else "Substring not found")

    # Check how many expected tokens appear in actual output
    hits    = [tok for tok in all_expected if tok in actual_output]
    score   = len(hits) / len(all_expected)
    missing = [tok for tok in all_expected if tok not in actual_output]

    reason = f"{len(hits)}/{len(all_expected)} key facts matched."
    if missing:
        reason += f" Missing: {', '.join(missing[:5])}"

    return round(score, 3), reason


def score_tool_selection(actual_tool_used: str, expected_tool: str) -> float:
    """
    Returns 1.0 if the correct tool was called, 0.0 otherwise.
    Pass None for actual_tool_used if you can't detect it from the response.
    """
    if actual_tool_used is None:
        return -1.0  # Unknown — will not log this score
    return 1.0 if actual_tool_used.strip() == expected_tool.strip() else 0.0


# ─────────────────────────────────────────────
# STEP 4 — Main experiment loop
# ─────────────────────────────────────────────
def run_experiment():
    logger.info("Loading dataset '%s' from Langfuse...", DATASET_NAME)
    dataset = langfuse.get_dataset(DATASET_NAME)
    items   = dataset.items

    if not items:
        logger.error("Dataset is empty. Make sure you uploaded your CSV correctly in Langfuse.")
        return

    logger.info("Found %d dataset items. Starting experiment run '%s'...\n", len(items), EXPERIMENT_RUN)

    results = []

    for item in items:
        # Each dataset item has: item.input, item.expected_output, item.metadata
        # Your CSV columns map like this after upload:
        #   input         → {"query": "...", "category": "..."}
        #   expected_output → {"expected_tool": "...", "expected_answer": "..."}

        inp      = item.input or {}
        exp      = item.expected_output or {}

        query           = inp.get("query", "")
        category        = inp.get("category", "unknown")
        expected_tool   = exp.get("expected_tool", "")
        expected_answer = exp.get("expected_answer", "")

        if not query:
            logger.warning("Skipping item %s — no query found in input", item.id)
            continue

        logger.info("[%s] %s", category.upper(), query[:80])

        # ── item.run() creates a trace in Langfuse and links it to this dataset run ──
        with item.run(
            run_name=EXPERIMENT_RUN,
            run_description=f"Automated eval — TrakSYS MCP baseline",
            run_metadata={"server_url": MCP_SERVER_URL},
        ) as root_span:

            # 1. Call the MCP tool
            t_start      = time.monotonic()
            actual_output = call_mcp_tool(expected_tool, query)
            latency_ms   = round((time.monotonic() - t_start) * 1000)

            logger.info("  → Response (%dms): %s", latency_ms, actual_output[:120])

            # 2. Update the trace with actual input/output for Langfuse UI
            root_span.update(
                input={"query": query, "tool": expected_tool},
                output={"response": actual_output},
                metadata={
                    "category": category,
                    "latency_ms": latency_ms,
                    "expected_answer": expected_answer,
                },
            )

            # 3. Score: answer correctness (keyword match, 0.0 → 1.0)
            answer_score, answer_reason = score_keyword_match(actual_output, expected_answer)
            root_span.score_trace(
                name="answer_correctness",
                value=answer_score,
                comment=answer_reason,
            )
            logger.info("  ✓ answer_correctness=%.2f  %s", answer_score, answer_reason)

            # 4. Score: latency bucket (1.0 = fast <2s, 0.5 = ok <5s, 0.0 = slow)
            if latency_ms < 2000:
                latency_score = 1.0
            elif latency_ms < 5000:
                latency_score = 0.5
            else:
                latency_score = 0.0

            root_span.score_trace(
                name="latency_ok",
                value=latency_score,
                comment=f"{latency_ms}ms",
            )

            # Track for summary
            results.append({
                "query":          query,
                "category":       category,
                "expected_tool":  expected_tool,
                "expected_answer":expected_answer,
                "actual_output":  actual_output,
                "answer_score":   answer_score,
                "latency_ms":     latency_ms,
                "passed":         answer_score >= 0.6,   # ≥60% facts matched = pass
            })

    # ─────────────────────────────────────────────
    # STEP 5 — Print summary report
    # ─────────────────────────────────────────────
    print("\n" + "="*70)
    print(f"  EXPERIMENT: {EXPERIMENT_RUN}")
    print("="*70)

    total  = len(results)
    passed = sum(1 for r in results if r["passed"])
    avg_score = sum(r["answer_score"] for r in results) / total if total else 0
    avg_latency = sum(r["latency_ms"] for r in results) / total if total else 0

    print(f"\n  Overall accuracy : {passed}/{total} passed  ({passed/total*100:.1f}%)")
    print(f"  Avg answer score : {avg_score:.2f} / 1.00")
    print(f"  Avg latency      : {avg_latency:.0f}ms\n")

    # Breakdown by category
    categories = sorted(set(r["category"] for r in results))
    print("  By category:")
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        cat_passed  = sum(1 for r in cat_results if r["passed"])
        cat_avg     = sum(r["answer_score"] for r in cat_results) / len(cat_results)
        print(f"    {cat:<15}  {cat_passed}/{len(cat_results)}  avg={cat_avg:.2f}")

    # Failed cases
    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n  ❌ Failed cases ({len(failed)}):")
        for r in failed:
            print(f"    [{r['category']}] {r['query'][:60]}")
            print(f"      expected: {r['expected_answer'][:80]}")
            print(f"      got     : {r['actual_output'][:80]}\n")
    else:
        print("\n  ✅ All cases passed!")

    print("="*70)
    print(f"\n  Open Langfuse → Datasets → {DATASET_NAME} → Runs")
    print(f"  to see the full scored experiment run: '{EXPERIMENT_RUN}'\n")

    # Flush all pending scores to Langfuse
    langfuse.flush()


# ─────────────────────────────────────────────
# HOW TO STRUCTURE YOUR LANGFUSE DATASET ITEMS
# ─────────────────────────────────────────────
# When you upload the CSV, map columns like this in the Langfuse UI:
#
#   CSV column "query"           → input.query
#   CSV column "category"        → input.category
#   CSV column "expected_tool"   → expected_output.expected_tool
#   CSV column "expected_answer" → expected_output.expected_answer
#   CSV column "notes"           → metadata.notes
#
# Or use the helper below to upload items via SDK instead of the UI:

def upload_csv_to_langfuse(csv_path: str):
    """
    Alternative: upload your CSV programmatically instead of using the UI.
    Run once, then use run_experiment() for all future runs.

    Usage:
        upload_csv_to_langfuse("traksys_eval.csv")
    """
    import csv

    langfuse.create_dataset(
        name=DATASET_NAME,
        description="TrakSYS MCP tool evaluation — 27 ground-truth test cases",
        metadata={"source": "traksys_eval.csv", "project": "KdG AG Solution Group"},
    )

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            langfuse.create_dataset_item(
                dataset_name=DATASET_NAME,
                input={
                    "query":    row["query"],
                    "category": row["category"],
                },
                expected_output={
                    "expected_tool":   row["expected_tool"],
                    "expected_answer": row["expected_answer"],
                },
                metadata={
                    "id":    row["id"],
                    "notes": row.get("notes", ""),
                },
            )

    logger.info("Uploaded %s to Langfuse dataset '%s'", csv_path, DATASET_NAME)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--upload":
        # First-time setup: upload CSV
        # python traksys_eval.py --upload traksys_eval.csv
        csv_file = sys.argv[2] if len(sys.argv) > 2 else "traksys_eval.csv"
        upload_csv_to_langfuse(csv_file)
    else:
        # Run experiment
        run_experiment()