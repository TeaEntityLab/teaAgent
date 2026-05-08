from __future__ import annotations

import http.client
import json
import os


def main() -> None:
    token = os.environ["MCP_TOKEN"]
    conn = http.client.HTTPConnection("127.0.0.1", 7330, timeout=10)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    conn.request(
        "POST",
        "/mcp",
        body=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        },
    )
    response = conn.getresponse()
    print(response.status, response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
