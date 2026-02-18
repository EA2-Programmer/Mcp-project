import asyncio
import json
import httpx
import re


async def test_server():
    async with httpx.AsyncClient() as client:
        # Get session
        print("Getting session...")
        resp = await client.get(
            "http://localhost:8080/mcp",
            headers={"Accept": "text/event-stream"}
        )
        session_id = resp.headers.get("mcp-session-id")
        print(f"Session ID: {session_id}")

        if not session_id:
            print("❌ No session ID")
            return

        # Initialize
        print("\nInitializing...")
        init = await client.post(
            "http://localhost:8080/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "0.1.0",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                },
                "id": 1
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id
            }
        )
        print(f"Init status: {init.status_code}")

        # List tools
        print("\nListing tools...")
        tools = await client.post(
            "http://localhost:8080/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id
            }
        )

        # Parse the SSE response properly
        text = tools.text
        print(f"Raw response preview: {text[:150]}...")

        # Extract JSON from SSE format
        if text.startswith("event: message"):
            # Find the data line and extract JSON
            data_match = re.search(r"data: ({.*})", text, re.DOTALL)
            if data_match:
                json_str = data_match.group(1)
                try:
                    result = json.loads(json_str)
                    print("\n✅ Success! Parsed response:")
                    print(json.dumps(result, indent=2)[:500] + "...")  # Show first 500 chars

                    if "result" in result and "tools" in result["result"]:
                        tools_list = result["result"]["tools"]
                        print(f"\n✅ Found {len(tools_list)} tools:")
                        for tool in tools_list:
                            print(f"  - {tool['name']}")
                except json.JSONDecodeError as e:
                    print(f"❌ JSON parse error: {e}")
                    print(f"Problem JSON string: {json_str[:200]}")
            else:
                print("❌ Could not find JSON data in response")
        else:
            print(f"Unexpected response format: {text[:200]}")


asyncio.run(test_server())