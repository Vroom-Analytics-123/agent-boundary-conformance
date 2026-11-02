"""Protocol tests for the FinePrint MCP server (mcp/server.py).

Spawns the real server over stdio and speaks MCP: initialize, tools/list,
and one tools/call per tool. run_check is exercised with --only FP-001
(~7s) so the suite stays fast; the full runner is covered by
test_fineprint_check.py.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "mcp" / "server.py"


class MCPClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def call(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def tool(self, name, args):
        resp = self.call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": name, "arguments": args}})
        assert "error" not in resp, resp
        assert resp["result"].get("isError") is not True, resp
        return json.loads(resp["result"]["content"][0]["text"])

    def close(self):
        self.proc.stdin.close()
        assert self.proc.wait(timeout=10) == 0


def test_mcp_protocol_end_to_end():
    c = MCPClient()
    try:
        init = c.call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": "2024-11-05"}})
        assert init["result"]["serverInfo"]["name"] == "fineprint"
        tools = c.call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in tools["result"]["tools"]]
        assert names == ["check_command", "list_invariants",
                         "measurement_routes", "run_check"]

        cases = [("rm -rf /tmp/x", "forbidden"),
                 ("git status", "allow"),
                 ("deployctl release", "prompt"),
                 ("cat /etc/passwd", "unknown"),
                 ("rm -rf /tmp/x && echo done", "forbidden")]
        for command, expected in cases:
            verdict = c.tool("check_command", {"command": command})
            assert verdict["decision"] == expected, (command, verdict)

        inv = c.tool("list_invariants", {})
        assert inv["count"] == 16
        assert inv["invariants"][0]["id"] == "FP-001"

        routes = c.tool("measurement_routes", {"harness": "codex"})
        assert routes["harnesses"][0]["measurement_route"] == "vendor-confirmed"

        run = c.tool("run_check", {"harness": "codex", "only": "FP-001"})
        assert run["exit_code"] == 0
        assert run["scorecard"]["schema_version"] == "fineprint-check-scorecard.v1"
    finally:
        c.close()
