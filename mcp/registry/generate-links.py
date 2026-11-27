#!/usr/bin/env python3
"""Generate the FinePrint MCP one-click install links + manual configs.

The FinePrint MCP server is a stdio server: `python3 mcp/server.py`
from a repo checkout. It has no npm/PyPI package and no hosted
endpoint, so the install links carry the checkout path — replace
<checkout-path> with the user's own checkout before sharing a link.

Usage:
    python3 mcp/registry/generate-links.py [--checkout PATH]

With no --checkout it emits the links with the placeholder path, so
the shape is reviewable without a real machine path in it.

It also validates mcp/registry/server.json against the constraints
of the official schema (2025-12-11, fetched 2026-11-08):
name matches ^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$, description is
1-100 chars, version is a plain string, repository has url+source.

NOT a publish step. Publishing needs Anish's word, a published
package first (the registry checks the package exists and carries
the server name), and his GitHub org-owner login — see README.md.
"""
import argparse
import base64
import json
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER_JSON = HERE / "server.json"
PLACEHOLDER = "/absolute/path/to/agent-boundary-conformance"

NAME_RE = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")


def validate_server_json():
    """Mirror the 2025-12-11 schema's required fields + patterns."""
    data = json.loads(SERVER_JSON.read_text())
    problems = []
    if not isinstance(data.get("name"), str) or not NAME_RE.match(data["name"]):
        problems.append(f"name {data.get('name')!r} must match "
                        "^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
    desc = data.get("description")
    if not isinstance(desc, str) or not 1 <= len(desc) <= 100:
        problems.append(f"description must be 1-100 chars, got "
                        f"{len(desc) if isinstance(desc, str) else desc!r}")
    if not isinstance(data.get("version"), str) or not data["version"]:
        problems.append("version must be a non-empty string")
    repo = data.get("repository") or {}
    if not repo.get("url") or not repo.get("source"):
        problems.append("repository needs url + source")
    return data, problems


def links_for(checkout):
    server_py = f"{checkout}/mcp/server.py"
    # Cursor: base64 of the SINGLE server object (the inner value of
    # mcpServers, without the name wrapping it). Verified against
    # cursor.com/docs/mcp/install-links.
    cursor_config = {"type": "stdio", "command": "python3",
                     "args": [server_py]}
    cursor_b64 = base64.b64encode(
        json.dumps(cursor_config, separators=(",", ":")).encode()
    ).decode()
    cursor = ("cursor://anysphere.cursor-deeplink/mcp/install"
              f"?name=fineprint&config={cursor_b64}")
    # VS Code: URL-encoded JSON of the server entry WITH its name.
    # Verified against the VS Code install-link docs + the blender-mcp
    # example shape {"name","type":"stdio","command","args"}.
    vscode_config = {"name": "fineprint", "type": "stdio",
                     "command": "python3", "args": [server_py]}
    vscode = ("vscode://mcp/install?"
              + urllib.parse.quote(
                  json.dumps(vscode_config, separators=(",", ":")),
                  safe=""))
    return cursor_config, vscode_config, cursor, vscode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkout", default=PLACEHOLDER,
                    help="repo checkout path baked into the links")
    args = ap.parse_args()
    data, problems = validate_server_json()
    if problems:
        print("server.json INVALID:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"server.json OK: {data['name']} {data['version']} "
          f"(description {len(data['description'])}/100 chars)")
    cursor_config, vscode_config, cursor, vscode = links_for(args.checkout)
    print()
    print("Cursor (base64 of the single server object):")
    print(f"  config: {json.dumps(cursor_config)}")
    print(f"  link:   {cursor}")
    print()
    print("VS Code (URL-encoded JSON, name included):")
    print(f"  config: {json.dumps(vscode_config)}")
    print(f"  link:   {vscode}")
    print()
    print("Manual configs (same server, no link):")
    print("  Cursor / Claude Code (.cursor/mcp.json, .mcp.json):")
    print("  " + json.dumps(
        {"mcpServers": {"fineprint": cursor_config}}, indent=2
    ).replace("\n", "\n  "))
    print("  VS Code (.vscode/mcp.json, top-level key is 'servers'):")
    print("  " + json.dumps(
        {"servers": {"fineprint": vscode_config}}, indent=2
    ).replace("\n", "\n  "))
    print("  Codex (~/.codex/config.toml):")
    print("  [mcp_servers.fineprint]")
    print('  command = "python3"')
    print(f"  args = [\"{args.checkout}/mcp/server.py\"]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
