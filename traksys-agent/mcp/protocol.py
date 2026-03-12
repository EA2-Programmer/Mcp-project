import json
from typing import Any, Dict, Optional

class JSONRPCHelper:
    """Helpers for creating and parsing JSON-RPC 2.0 messages for MCP."""
    
    @staticmethod
    def create_request(method: str, params: Optional[Dict[str, Any]] = None, request_id: int = 1) -> str:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id
        }
        return json.dumps(payload) + "\n"

    @staticmethod
    def parse_response(line: str) -> Dict[str, Any]:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON", "raw": line}
