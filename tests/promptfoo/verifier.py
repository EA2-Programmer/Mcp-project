"""
Database verifier for TrakSYS MCP tests.
Entry point for promptfoo python assertions: get_assert(output, context)
"""
import json
import re
import os
from typing import Dict, Any, List, Optional


CONNECTION_STRING = os.getenv(
    "MSSQL_CONNECTION_STRING",
    "Driver={ODBC Driver 17 for SQL Server};Server=localhost,1433;"
    "Database=EBR_Template;UID=traksys_app;PWD=TrakSYS99!;TrustServerCertificate=yes",
)


def get_db_connection():
    import pyodbc
    return pyodbc.connect(CONNECTION_STRING, timeout=30)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_str(output: Any) -> str:
    """
    Promptfoo passes output as a dict when the API returns JSON,
    or as a string otherwise. Always normalise to string.
    """
    if isinstance(output, (dict, list)):
        return json.dumps(output)
    return str(output) if output is not None else ""


def parse_output(output: Any) -> Any:
    """Return parsed JSON if possible, otherwise the raw string."""
    if isinstance(output, (dict, list)):
        return output  # already parsed by promptfoo
    try:
        return json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return output


def extract_numbers(text: Any) -> List[float]:
    """
    Extract decimal numbers (1-3 digits before decimal) from text.
    Uses List[float] not list[float] — compatible with Python 3.8/3.9.
    Avoids grabbing 4-digit IDs, years, ports, etc.
    """
    raw = re.findall(r"\b(\d{1,3}(?:\.\d+)?)\b", to_str(text))
    return [float(x) for x in raw]


def find_value_in_json(data: Any, *keys: str) -> Optional[float]:
    """Recursively find first numeric value for any of the given keys (case-insensitive)."""
    lower_keys = [k.lower() for k in keys]
    if isinstance(data, dict):
        for k, v in data.items():
            if k.lower() in lower_keys:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
            result = find_value_in_json(v, *keys)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_value_in_json(item, *keys)
            if result is not None:
                return result
    return None


def numbers_close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# Category verifiers
# ---------------------------------------------------------------------------

def verify_oee(output: Any, expected: str, tolerance: float = 0.5) -> Dict[str, Any]:
    """
    Handle three OEE expected formats:
      - Single value:        "97.3"
      - Component breakdown: "A:99.0, P:98.9, Q:99.4"
      - Multi-line compare:  "E1:97.3, E2:90.6"
    """
    parsed = parse_output(output)
    raw_str = to_str(output)
    expected = expected.strip()

    # Component breakdown: "A:99.0, P:98.9, Q:99.4"
    component_pattern = re.findall(r"([A-Za-z]+)\s*:\s*(\d+\.?\d*)", expected)
    if len(component_pattern) > 1:
        label_map = {"A": "availability", "P": "performance", "Q": "quality"}
        failures = []
        for idx, (label, exp_val) in enumerate(component_pattern):
            exp_f = float(exp_val)
            full_name = label_map.get(label.upper(), label)
            got = find_value_in_json(parsed, label, label.lower(), full_name)
            if got is None:
                nums = extract_numbers(raw_str)
                got = nums[idx] if idx < len(nums) else None
            if got is None:
                failures.append(f"{label}: expected {exp_f}, got <missing>")
            elif not numbers_close(got, exp_f, tolerance):
                failures.append(f"{label}: expected {exp_f}, got {got}, diff={abs(got-exp_f):.2f}")
        if failures:
            return {"pass": False, "reason": "Component mismatch: " + "; ".join(failures)}
        return {"pass": True, "reason": f"All components within tolerance ({tolerance})"}

    # Multi-line: "E1:97.3, E2:90.6"
    line_pattern = re.findall(r"(E\d+)\s*:\s*(\d+\.?\d*)", expected)
    if line_pattern:
        failures = []
        for idx, (line_name, exp_val) in enumerate(line_pattern):
            exp_f = float(exp_val)
            got = find_value_in_json(parsed, line_name, line_name.lower(), "oee", "value")
            if got is None:
                nums = extract_numbers(raw_str)
                got = nums[idx] if idx < len(nums) else None
            if got is None:
                failures.append(f"{line_name}: expected {exp_f}, got <missing>")
            elif not numbers_close(got, exp_f, tolerance):
                failures.append(f"{line_name}: expected {exp_f}, got {got}, diff={abs(got-exp_f):.2f}")
        if failures:
            return {"pass": False, "reason": "Line comparison mismatch: " + "; ".join(failures)}
        return {"pass": True, "reason": f"All lines within tolerance ({tolerance})"}

    # Single value: "97.3"
    expected_nums = extract_numbers(expected)
    if not expected_nums:
        return {"pass": False, "reason": f"Cannot parse expected OEE: '{expected}'"}
    exp_f = expected_nums[0]

    got = find_value_in_json(parsed, "oee", "oee_value", "value", "result", "overall")
    if got is None:
        nums = extract_numbers(raw_str)
        got = nums[0] if nums else None

    if got is None:
        return {"pass": False, "reason": f"No OEE number in output: {raw_str[:200]}"}

    diff = abs(got - exp_f)
    return {
        "pass": diff <= tolerance,
        "reason": f"Expected {exp_f}, got {got}, diff={diff:.2f} (tol={tolerance})",
    }


def verify_downtime_total(output: Any, expected_minutes: float, tolerance: float = 5.0) -> Dict[str, Any]:
    parsed = parse_output(output)
    raw_str = to_str(output)

    got = find_value_in_json(parsed, "total_minutes", "total", "duration", "minutes", "downtime")
    if got is None:
        nums = extract_numbers(raw_str)
        got = max(nums) if nums else None

    if got is None:
        return {"pass": False, "reason": f"No downtime total in output: {raw_str[:200]}"}

    diff = abs(got - expected_minutes)
    return {
        "pass": diff <= tolerance,
        "reason": f"Expected ~{expected_minutes} min, got {got:.0f} min, diff={diff:.0f}",
    }


def verify_downtime_events(output: Any, expected: str) -> Dict[str, Any]:
    raw_str = to_str(output)
    event_names = re.findall(r"([A-Za-z][A-Za-z\s]+?)\s*\(", expected)
    if not event_names:
        return {"pass": len(raw_str) > 50, "reason": "Non-empty downtime event response"}
    missing = [n.strip() for n in event_names if n.strip().lower() not in raw_str.lower()]
    if missing:
        return {"pass": False, "reason": f"Missing events: {', '.join(missing)}"}
    return {"pass": True, "reason": f"All {len(event_names)} events found"}


def verify_downtime_longest(output: Any, expected: str) -> Dict[str, Any]:
    raw_str = to_str(output)
    match = re.match(r"([A-Za-z][A-Za-z\s]+?)\s*\((\d+)\s*min\)", expected.strip())
    if not match:
        return {"pass": expected.lower() in raw_str.lower(), "reason": f"Substring check"}
    event_name, duration_str = match.group(1).strip(), match.group(2)
    name_found = event_name.lower() in raw_str.lower()
    dur_found = duration_str in raw_str
    return {
        "pass": name_found and dur_found,
        "reason": f"'{event_name}' {'ok' if name_found else 'missing'}, {duration_str}min {'ok' if dur_found else 'missing'}",
    }


def verify_batch_found(output: Any, expected: str) -> Dict[str, Any]:
    raw_str = to_str(output)
    expected_ids = re.findall(r"\b(\d{3,})\b", expected)
    if not expected_ids:
        return {"pass": len(raw_str) > 20, "reason": "Non-empty batch response"}
    missing = [bid for bid in expected_ids if bid not in raw_str]
    if missing:
        return {"pass": False, "reason": f"Missing batch IDs: {', '.join(missing)}"}
    return {"pass": True, "reason": f"All batch IDs found: {', '.join(expected_ids)}"}


def verify_quality(output: Any, expected: str) -> Dict[str, Any]:
    raw_str = to_str(output)
    expected_lower = expected.lower()
    output_lower = raw_str.lower()

    # Yes/No
    if expected_lower.startswith("yes") or expected_lower.startswith("no"):
        keyword = "yes" if expected_lower.startswith("yes") else "no"
        return {"pass": keyword in output_lower, "reason": f"Expected '{keyword}' in output"}

    # Deviation counts: "Batch 456: 0 deviations"
    deviation_pattern = re.findall(r"batch\s+(\d+).*?(\d+)\s+deviation", expected_lower)
    if deviation_pattern:
        failures = []
        for batch_id, exp_devs in deviation_pattern:
            found = re.search(rf"batch\s+{batch_id}.*?(\d+)\s+deviation", output_lower)
            if not found:
                failures.append(f"Batch {batch_id}: info not found")
            elif found.group(1) != exp_devs:
                failures.append(f"Batch {batch_id}: expected {exp_devs}, got {found.group(1)}")
        if failures:
            return {"pass": False, "reason": "; ".join(failures)}
        return {"pass": True, "reason": "Deviation counts match"}

    # Keyword ratio
    stop = {"with", "from", "that", "this", "have", "were", "been", "only",
            "show", "both", "than", "some", "more", "each"}
    keywords = [w for w in re.findall(r"[A-Za-z]{4,}", expected) if w.lower() not in stop]
    if keywords:
        found = [w for w in keywords if w.lower() in output_lower]
        ratio = len(found) / len(keywords)
        return {
            "pass": ratio >= 0.6,
            "reason": f"{len(found)}/{len(keywords)} keywords ({ratio*100:.0f}%) — need >=60%",
        }

    return {"pass": expected_lower in output_lower, "reason": f"Substring: '{expected[:80]}'"}


def verify_materials(output: Any, expected: str) -> Dict[str, Any]:
    raw_str = to_str(output)
    material_nums = re.findall(r"[Mm]aterial\s+(\d+)", expected)
    if not material_nums:
        return verify_quality(output, expected)
    missing = [n for n in material_nums if n not in raw_str]
    if missing:
        return {"pass": False, "reason": f"Missing material numbers: {', '.join(missing)}"}
    return {"pass": True, "reason": f"All {len(material_nums)} materials found"}


def verify_tasks(output: Any, expected: str) -> Dict[str, Any]:
    raw_str = to_str(output)
    numbers = extract_numbers(expected)
    if not numbers:
        return verify_quality(output, expected)
    output_nums = extract_numbers(raw_str)
    missing = [n for n in numbers if not any(numbers_close(o, n, 2) for o in output_nums)]
    if missing:
        return {"pass": False, "reason": f"Expected counts {missing} not found (+-2 tol)"}
    return {"pass": True, "reason": f"All counts found: {numbers}"}


def verify_equipment(output: Any, expected: str) -> Dict[str, Any]:
    raw_str = to_str(output)
    stop = {"with", "and", "the", "for", "are", "not", "its", "any"}
    keywords = [k for k in re.findall(r"[A-Za-z]{3,}", expected) if k.lower() not in stop]
    if not keywords:
        return {"pass": len(raw_str) > 20, "reason": "Non-empty equipment response"}
    found = [k for k in keywords if k.lower() in raw_str.lower()]
    ratio = len(found) / len(keywords)
    return {
        "pass": ratio >= 0.5,
        "reason": f"{len(found)}/{len(keywords)} keywords ({ratio*100:.0f}%) — need >=50%",
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def verify_test(output: Any, vars: Dict) -> Dict[str, Any]:
    """Route to the correct verifier based on category."""
    category  = (vars.get("category") or "").lower().strip()
    expected  = str(vars.get("expected_answer") or "").strip()
    query     = (vars.get("query") or "").lower()
    tolerance = float(vars.get("tolerance") or 0.5)

    if category == "oee":
        return verify_oee(output, expected, tolerance)

    if category == "downtime":
        if "total" in query or "how much" in query:
            nums = extract_numbers(expected)
            return verify_downtime_total(output, nums[0] if nums else 0)
        elif "longest" in query:
            return verify_downtime_longest(output, expected)
        else:
            return verify_downtime_events(output, expected)

    if category == "batches":
        return verify_batch_found(output, expected)

    if category == "quality":
        return verify_quality(output, expected)

    if category == "materials":
        return verify_materials(output, expected)

    if category == "tasks":
        return verify_tasks(output, expected)

    if category == "equipment":
        return verify_equipment(output, expected)

    if category == "jobs":
        return verify_batch_found(output, expected)

    if expected:
        return {"pass": expected.lower() in to_str(output).lower(),
                "reason": f"Default substring: '{expected[:80]}'"}

    return {"pass": len(to_str(output)) > 10, "reason": "Non-empty response check"}


# ---------------------------------------------------------------------------
# Promptfoo entry point — must be named get_assert
# ---------------------------------------------------------------------------

def get_assert(output: Any, context: dict) -> dict:
    """
    Called by promptfoo for `type: python` assertions.
    - output: dict if API returned JSON, string otherwise
    - context: contains 'vars' (the CSV row), 'prompt', etc.
    """
    try:
        result = verify_test(output, context.get("vars", {}))
        return {
            "pass": bool(result.get("pass", False)),
            "reason": result.get("reason", ""),
            "score": 1.0 if result.get("pass") else 0.0,
        }
    except Exception as exc:
        return {
            "pass": False,
            "reason": f"Verifier exception: {type(exc).__name__}: {exc}",
            "score": 0.0,
        }