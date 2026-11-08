# FinePrint MCP server — Registry entry + one-click install links

**Prepared, NOT submitted.** Publishing is a public act and needs
Anish's explicit word. Nothing here has been sent to the registry.

## What the server is — labelled honestly

The FinePrint MCP server (`mcp/server.py`, stdio, Python stdlib only)
is **advisory check-and-report, never enforcement**. It exposes four
tools to an MCP-compatible host:

- `check_command` — decision-layer verdict for one command against a
  policy (FinePrint's own simplified prefix evaluator; it does not
  invoke any vendor's native decision checker)
- `list_invariants` — the FinePrint catalogue invariants
- `measurement_routes` — per-harness measurement route + provenance
  (unranked)
- `run_check` — run a full sealed conformance check, return its
  scorecard

It can tell an agent (or a developer) whether a command looks allowed
by the rules. It cannot stop anything: it sees only calls to its own
tools and cannot intercept the host's native Read/Bash/Edit tools.
Any surface that calls this enforcement is wrong — including this
README, the registry description, and the install links. The wall
(`fineprint gate run`) is the enforcement; this server is the
check-and-report companion.

## The registry entry

`server.json` follows the official schema
(`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`,
fetched 2026-11-08):

- **name:** `io.github.vroom-analytics-123/fineprint`
- **description:** "Decision-layer checks for whether a coding
  agent's rules hold, from measured evidence." (86/100 chars)
- **version:** `0.1.0` — the entry's first version; the server itself
  reports no version
- **repository:** github,
  `https://github.com/Vroom-Analytics-123/agent-boundary-conformance`,
  subfolder `mcp`
- **No `packages`, no `remotes`.** The server runs from a repo
  checkout (`python3 mcp/server.py`); there is no npm/PyPI package
  and no hosted endpoint. The schema does not require either field.

## One-click install links

`generate-links.py` emits both links plus the manual configs:

```sh
python3 mcp/registry/generate-links.py --checkout /path/to/agent-boundary-conformance
```

- **Cursor:**
  `cursor://anysphere.cursor-deeplink/mcp/install?name=fineprint&config=<base64>`
  where `config` is the base64 of the single server object
  `{"type":"stdio","command":"python3","args":["<checkout>/mcp/server.py"]}`
  (verified against cursor.com/docs/mcp/install-links). Clicking it
  opens Cursor, which prompts before installing; deeplinks never
  execute anything automatically.
- **VS Code:**
  `vscode://mcp/install?<url-encoded JSON>` where the JSON is the
  server entry with its name:
  `{"name":"fineprint","type":"stdio","command":"python3","args":["<checkout>/mcp/server.py"]}`
  (verified against the VS Code install-link docs and the blender-mcp
  example shape). One project reports the link misbehaving on some VS
  Code builds (creating a broken `my-mcp-server-*` entry) — the
  manual `.vscode/mcp.json` entry the generator also prints is the
  fallback that always works.

**The checkout-path caveat, stated plainly:** both links embed the
absolute path to the user's repo checkout, which the link author
cannot know. A link shared with the placeholder path installs a
broken server. Generate the links with the real checkout path
(`--checkout`), or use the manual configs. A truly path-free
one-click install needs a published package (see below).

## How to submit (when Anish says so)

1. **Publish a package first.** The registry is metadata-only and
   checks at publish time that the package the entry names exists
   and carries the server name (an `mcpName` field for npm, an
   `mcp-name:` line for PyPI). There is no FinePrint package yet —
   this is the blocker, not the `server.json`. Until a package
   exists, `server.json` has no `packages` entry to point at.
2. Install the publisher: `brew install mcp-publisher`, or the
   binary from
   `github.com/modelcontextprotocol/registry/releases`.
3. Validate (no login needed):
   `mcp-publisher validate mcp/registry/server.json`
4. Log in (device flow; the namespace `io.github.vroom-analytics-123/*`
   needs the GitHub org Owner — a classic PAT with `read:org`):
   `mcp-publisher login github`
5. Publish: `mcp-publisher publish mcp/registry/server.json`
6. Verify: search the registry for
   `io.github.vroom-analytics-123/fineprint`.

The registry is in preview; breaking changes or data resets may occur
before general availability.
