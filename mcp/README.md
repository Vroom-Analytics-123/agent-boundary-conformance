# FinePrint MCP server

`server.py` is a stdio MCP server (Python stdlib only, no dependencies).
It exposes the FinePrint measurement engine to any MCP-compatible agent
client as four tools: `check_command`, `list_invariants`,
`measurement_routes`, `run_check`. See [SKILL.md](SKILL.md) for how an
agent should use them — including the honesty rules (unknown is never
allow; reconstructed is evaluation, never interrogation).

## Run it

```bash
python3 mcp/server.py   # speaks newline-delimited JSON-RPC 2.0 on stdio
```

It needs this repo checked out (it reads the catalogue, the measurement
routes, and the default policy from the repo) and Python 3.12. Nothing
executes: `check_command` evaluates policy text, and `run_check` runs the
repo's own check runner, which only probes a decision oracle.

Two things `check_command` is not. It is FinePrint's own simplified
prefix evaluator over policy text — it does not invoke any vendor's
native decision checker. The full measurement runner (the harness
runners and `tools/run_fixtures.py`) is the part that replays probes
against each harness's own native policy checker; that is the evidence
badges rest on. A `check_command` verdict is a quick decision-layer
check, not a measurement result.

## Claude Code

Add to `.mcp.json` in your project (or `~/.claude.json` for a user scope):

```json
{ "mcpServers": { "fineprint": {
    "command": "python3",
    "args": ["/absolute/path/to/agent-boundary-conformance/mcp/server.py"] } } }
```

A ready example is in [examples/claude-mcp.json](examples/claude-mcp.json)
(fill in your checkout path).

## Codex

Add to `~/.codex/config.toml` (see [examples/codex-config.toml](examples/codex-config.toml)):

```toml
[mcp_servers.fineprint]
command = "python3"
args = ["/absolute/path/to/agent-boundary-conformance/mcp/server.py"]
```

## Any other MCP-compatible client

Use the same stdio command above: `python3 <checkout>/mcp/server.py`
with no arguments and no environment variables. If your client supports
stdio MCP servers, that is the whole integration. (Client-specific setup
for clients other than Claude Code and Codex is not verified here — the
generic stdio form is the supported surface.)

## Verify it

```bash
python3 -m pytest tests/test_mcp_server.py -q
```

That spawns the real server and speaks MCP end to end: initialize,
tools/list, one call per tool, including a real `run_check` scoped to
FP-001.
