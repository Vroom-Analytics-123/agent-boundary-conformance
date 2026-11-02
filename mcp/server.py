#!/usr/bin/env python3
"""FinePrint MCP server (stdio, stdlib only).

Exposes the FinePrint measurement engine to any MCP-compatible agent client
(Claude Code, Codex, or any client that speaks MCP over stdio) as four tools:

  check_command      Decision-layer verdict for one command against a policy.
                     Pure prefix evaluation, no oracle, nothing executes.
  list_invariants    The 16 catalogue invariants (id, name, family, intent).
  measurement_routes Per-harness measurement route + provenance (unranked).
  run_check          A full sealed check run via tools/fineprint_check.py.

Honesty rules the server never breaks (they are the method, not decoration):
  - unknown is never allow, never a bypass, never a hole.
  - a no-match serializes as unknown with layer attribution (Decision).
  - reconstructed results are evaluations from documented semantics, never
    interrogations of a live harness.
  - nothing here executes a command. check_command evaluates; run_check runs
    the repo's own check runner, which only probes a decision oracle.

Transport: newline-delimited JSON-RPC 2.0 on stdin/stdout (MCP stdio).
Usage:  python3 mcp/server.py
"""

import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SERVER_VERSION = "0.1.0"

RULE_RE = re.compile(
    r'prefix_rule\(\s*pattern=\[(.*?)\]\s*,\s*decision="(\w+)"\s*\)')
RANK = {"forbidden": 3, "prompt": 2, "allow": 1}


def parse_rules(text):
    """Parse prefix_rule(...) lines into [(pattern_tokens, decision)]."""
    rules = []
    for m in RULE_RE.finditer(text):
        toks = re.findall(r'"([^"]*)"', m.group(1))
        rules.append((toks, m.group(2)))
    return rules


def head_segment(command):
    """First segment of a compound command (INV-004: compounds are head-only)."""
    parts = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command.strip())
    return parts[0] if parts else ""


def evaluate(command, rules):
    """Most-restrictive-wins prefix match; no match -> unknown."""
    seg = head_segment(command)
    try:
        argv = shlex.split(seg)
    except ValueError:
        return {"decision": "unknown", "matched_rule": None,
                "note": "unparseable command serializes as unknown"}
    best = None
    for pattern, decision in rules:
        if pattern and argv[:len(pattern)] == pattern:
            if best is None or RANK[decision] > RANK[best[1]]:
                best = (pattern, decision)
    if best is None:
        return {"decision": "unknown", "matched_rule": None,
                "note": "no rule matched: unknown with Decision-layer attribution, "
                        "never allow, never a bypass"}
    return {"decision": best[1], "matched_rule": best[0],
            "note": "compound commands evaluate the head segment only" if seg != command.strip() else ""}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tool_check_command(args):
    command = args.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command (string) is required")
    policy = args.get("policy")
    if policy:
        rules = parse_rules(policy)
        if not rules:
            raise ValueError("policy text contains no prefix_rule(...) lines")
    else:
        rules = parse_rules((REPO / "fixtures/policies/default.rules").read_text())
    verdict = evaluate(command, rules)
    return {"command": command, "head_segment": head_segment(command),
            "layer": "Decision", **verdict}


def tool_list_invariants(args):
    data = load_json(REPO / "docs/catalogue/catalogue.json")
    only = args.get("only")
    entries = data["entries"]
    if only:
        wanted = set(only if isinstance(only, list) else [only])
        entries = [e for e in entries if e["id"] in wanted]
    return {"catalogue_version": data.get("catalogue_version"),
            "count": len(entries),
            "invariants": [{"id": e["id"], "name": e["name"],
                            "family": e["family"], "intent": e["intent"]}
                           for e in entries]}


def tool_measurement_routes(args):
    data = load_json(REPO / "docs/assets/measurement-routes-current.json")
    only = args.get("harness")
    hs = data["harnesses"]
    if only:
        hs = [h for h in hs if h["harness"] == only]
    return {"note": data["note"], "harnesses": hs}


def tool_run_check(args):
    harness = args.get("harness", "codex")
    only = args.get("only")
    out = Path(tempfile.mkdtemp(prefix="fineprint-check-"))
    cmd = [sys.executable, str(REPO / "tools/fineprint_check.py"),
           "--harness", harness,
           "--policy", str(REPO / "fixtures/policies/default.rules"),
           "--out", str(out)]
    if only:
        cmd += ["--only", only if isinstance(only, str) else ",".join(only)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return {"error": "check run timed out after 600s", "out_dir": str(out)}
    scorecard = {}
    sc = out / "scorecard.json"
    if sc.exists():
        scorecard = load_json(sc)
    return {"exit_code": proc.returncode, "harness": harness,
            "out_dir": str(out), "bundle": str(out / "bundle.json"),
            "scorecard": scorecard,
            "note": "Sealed bundle + scorecard are in out_dir. "
                    "A no-match in this run is unknown, never allow."}


TOOLS = {
    "check_command": ("Decision-layer verdict for one command against a policy. "
                      "Nothing executes. No match -> unknown, never allow.",
                      {"type": "object",
                       "properties": {
                           "command": {"type": "string"},
                           "policy": {"type": "string",
                                      "description": "Optional prefix_rule(...) text; "
                                                     "defaults to fixtures/policies/default.rules"}},
                       "required": ["command"]}),
    "list_invariants": ("List the FinePrint catalogue invariants.",
                        {"type": "object",
                         "properties": {"only": {"type": "array", "items": {"type": "string"}}}}),
    "measurement_routes": ("Per-harness measurement route + provenance (unranked).",
                           {"type": "object",
                            "properties": {"harness": {"type": "string"}}}),
    "run_check": ("Run a full sealed conformance check and return its scorecard.",
                  {"type": "object",
                   "properties": {
                       "harness": {"type": "string", "default": "codex"},
                       "only": {"type": "string",
                                "description": "Comma-separated invariant ids, e.g. FP-001,FP-002"}}}),
}

HANDLERS = {"check_command": tool_check_command,
            "list_invariants": tool_list_invariants,
            "measurement_routes": tool_measurement_routes,
            "run_check": tool_run_check}


def respond(req_id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            respond(None, error={"code": -32700, "message": "parse error"})
            continue
        method = req.get("method", "")
        req_id = req.get("id")
        if method.startswith("notifications/"):
            continue
        if method == "initialize":
            respond(req_id, result={
                "protocolVersion": req.get("params", {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fineprint", "version": SERVER_VERSION}})
        elif method == "tools/list":
            respond(req_id, result={"tools": [
                {"name": name, "description": desc, "inputSchema": schema}
                for name, (desc, schema) in TOOLS.items()]})
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            fn = HANDLERS.get(name)
            if fn is None:
                respond(req_id, error={"code": -32602, "message": f"unknown tool: {name}"})
                continue
            try:
                out = fn(params.get("arguments", {}))
                respond(req_id, result={"content": [{"type": "text", "text": json.dumps(out, indent=1)}]})
            except Exception as e:  # tool errors are results, not crashes
                respond(req_id, result={"content": [{"type": "text",
                                                     "text": json.dumps({"error": str(e)})}],
                                        "isError": True})
        elif method == "ping":
            respond(req_id, result={})
        else:
            respond(req_id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
