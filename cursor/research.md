# Cursor research — primary sources first

Checked 2026-11-01/02 (UTC 2026-11-02 06:15 fetch). All Cursor-doc
quotes below were read from Cursor's own docs pages on that fetch;
secondary claims are labeled as such and are NOT cited as evidence
for any verdict — only live runs are.

## PRIMARY: headless print mode (cursor.com/docs/cli/headless)

- Use print mode (`-p, --print`) for non-interactive scripting.
- "Combine `--print` with `--force` (or `--yolo`) to modify files in
  scripts."
- "Without --force, changes are only proposed, not applied" — and the
  example `agent -p "Add JSDoc comments to this file"  # Won't modify
  files`.
- "The `--force` flag allows the agent to make direct file changes
  without confirmation."
- Install: `curl https://cursor.com/install -fsS | bash`.
- Auth for scripts: `CURSOR_API_KEY` env var.
- Output formats: `text` (default in print mode), `json`,
  `stream-json`; `--stream-partial-output` with stream-json.
- Stream-json event set in the doc's own example includes `system`,
  `assistant`, `tool_call` (started/completed), `result` — no
  approval-request/response event pair is shown.

## PRIMARY: parameters (cursor.com/docs/cli/reference/parameters)

- `-p, --print`: "Print responses to console (for scripts or
  non-interactive use). Has access to all tools, including write and
  shell." — NOTE: this sentence CONFLICTS with the headless page's
  "without --force, only proposed" rule. The conflict is itself a
  finding: only a live run settles which page describes real
  behavior. The smoke is designed to settle it (Arm A).
- `--output-format`: `text`, `json`, `stream-json` (default `text`).
- `--model <model>`; `--mode`: `plan` or `ask` (agent is default).
- `-f, --force`: "Force allow commands unless explicitly denied".
- `--yolo`: alias for `--force`.
- `--sandbox <mode>`: `enabled` or `disabled`.
- `--approve-mcps`: auto-approve all MCP servers.
- `--trust`: "Trust the workspace without prompting (headless only)".
- `--workspace <path>`; `--api-key <key>` (or CURSOR_API_KEY).
- `agent acp`: "Start ACP server mode (advanced, hidden command)".
- `agent sandbox`: `enable` / `disable` ("Disable sandbox mode and use
  allowlist mode") / `reset` / `run <cmd>` with `--allow-paths`,
  `--readonly-paths`, `--blocked-patterns`, `--network` (default
  false), `--sb-debug`.
- `agent models` / `--list-models`: list available models.

## PRIMARY: using the CLI (cursor.com/docs/cli/using, via search excerpt)

- Interactively, "Before running terminal commands, CLI will ask you
  to approve (y) or reject (n) execution."
- `-p`/`--print` runs Agent in non-interactive mode, printing the
  response to the console.
- Agent tools: file operations, searching, shell commands, web
  access; MCP via `mcp.json`; rules via `.cursor/rules`, `AGENTS.md`.
- Modes: Agent (default), Plan, Ask.

## SECONDARY (corroborated across >=3 independent sources, NOT primary)

- Permissions files: global `~/.cursor/cli-config.json`, project
  `<project>/.cursor/cli.json` (project holds ONLY `permissions` and
  takes precedence for that key).
- Token grammar: `Shell(...)`, `Read(...)`, `Write(...)`,
  `WebFetch(...)`, `Mcp(...)`. `Shell(rm)` matches the rm command;
  deny wins over allow ("Deny rules take precedence over allow
  rules"). There are NO `--allow`/`--deny` runtime flags — permissions
  are config-file only.
- Untrusted workspaces in non-interactive runs fail with guidance
  unless `--trust` (or `--force`) is passed (Jan 2026 CLI changelog,
  via secondary summary).
- Team/org policy can disable "Run Everything" / headless CLI use
  server-side; when so, `--force` is refused and the CLI falls back
  to approval-required (allowlist) mode (Omniscio provider doc).
- `agent acp` is bidirectional JSON-RPC and COULD carry a real
  permission round-trip (klein-kit research, 2026-07-31, web-only).
  That is a custom-client integration, not the stock headless mode,
  and is out of scope for this bounded smoke; noted as a future path
  if a true approver interface is ever needed.
- The primary Cursor permissions page itself was NOT fetched in this
  pass (no verbatim URL returned by search); the deny-wins and token
  claims above therefore stay secondary until the live run confirms
  or refutes them. This is stated, not hidden.

## Conclusions for the harness

1. There is NO headless deny-all approver interface in stock Cursor
   CLI. Print mode either proposes without applying (no --force) or
   applies unless denied (with --force + deny list). There is no
   per-tool human/approver callback to drive.
2. The measurable strictest policies are Arm A (propose-only) and
   Arm B (deny-list under --force). Both are static/config policies,
   not decision policies — the scorecard must reflect that
   (policy-engine dimension: static lists, no runtime approver).
3. Auth is a hard gate: every run needs CURSOR_API_KEY. No such repo
   secret exists at smoke-build time; the owner must create it. A run
   without it is BLOCKED, not failed-on-merits.
4. Model: do NOT pin an unverified model ID. The runner records the
   model from the agent's own JSON output when present, else records
   `default-unrecorded`. `agent models` output is captured when it
   succeeds.
5. Sandbox: `--sandbox enabled` is the strictest available flag; its
   Linux-runner behavior is unproven and is itself an observation
   (started / failed / unknown — never assumed).
