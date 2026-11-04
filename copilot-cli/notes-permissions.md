# Copilot CLI permission / approval behavior — notes

Sources: the installed Copilot CLI 1.0.105 binary's own output
(`copilot --help`, `copilot help permissions`, `copilot help
environment`, 2026-11-03) first; GitHub Docs (install/auth pages)
second; third-party write-ups only where they agree with the binary.
Where help and docs disagree, help wins and the divergence is noted.
No token was used for any of this: version, help, and the no-token
probe need no auth.

## Layers

1. **Tool availability** (`--available-tools` / `--excluded-tools`):
   decides which tools the model can see at all. Not used by the smoke
   (all default tools visible).
2. **Tool approval** (`--allow-tool` / `--deny-tool` /
   `--allow-all-tools`): controls approval prompts. **Denial always
   takes precedence over allow rules, even --allow-all-tools.**
   `--allow-tool` / `--deny-tool` take a pattern `kind(argument)`:
   - `shell(command:*?)` — exact match on the command name; `:*`
     suffix matches prefixes on the command stem, e.g. `shell(git:*)`
     matches `git push` but not `gitea`. The smoke uses
     `shell(rm:*)` for direct rm invocations.
   - `write(path?)` — file create/modify tools except shell
     invocations; relative paths match by trailing components.
   - `<mcp-server>(tool?)` — a tool from a named MCP server.
   - `url(domain-or-url?)` — URL access, protocol-aware.
   `--deny-tool` tools "will not prompt for permission" — a denied
   tool is blocked, not asked about. That is the smoke's signal.
3. **URL permissions** (`--allow-url` / `--deny-url` /
   `--allow-all-urls`): protocol-aware; approving https does not
   approve http. Not used by the smoke (no URL task).
4. **Path permissions**: file access restricted to the working
   directory subtree plus the system temp dir by default.
   `--allow-all-paths` disables verification; `--disallow-temp-dir`
   removes temp-dir access. Neither is used by the smoke: the
   scratch tree sits inside the rundir (the working directory).
5. **All-permissions shortcuts** (`--allow-all` / `--yolo` =
   `--allow-all-tools --allow-all-paths --allow-all-urls`): NOT used
   by the smoke. Only `--allow-all-tools` is used, because -p
   requires it — and it is always paired with the deny rule.

## Non-interactive mode

- `-p / --prompt <text>`: one prompt, exits after completion.
- `--allow-all-tools` is REQUIRED for -p (help text verbatim:
  "required for non-interactive mode"). Without it, -p cannot
  proceed past approval prompts.
- `--no-ask-user`: disables the ask_user tool (agent works
  autonomously without asking questions). Used by the smoke so a
  turn cannot stall waiting for a question no human will answer.
- `--trust-folder`: trusts the working directory's configuration
  for one prompt-mode session only (no saved trust). Used by the
  smoke so a trust prompt cannot stall the turn. The rundir
  contains no skills/plugins/MCP configs, so nothing extra loads.
- `--output-format json`: JSONL, one JSON object per line. Used
  (without `-s`) so tool traces stay in the record.
- `--no-auto-update`: runs the bundled version rather than a newer
  downloaded one. Used so the pinned 1.0.105 stays the measured
  version. (Auto-update is already disabled by default in CI, but
  the flag makes it explicit.)
- `--secret-env-vars=COPILOT_GITHUB_TOKEN`: strips the named var
  from shell/MCP tool environments and redacts it from output.
  This is a safety measure, not a permission measurement.

## Environment variables that matter

- `COPILOT_GITHUB_TOKEN` > `GH_TOKEN` > `GITHUB_TOKEN`: auth
  token precedence (verified in `help environment`). The harness
  auth is the first; the other two are recorded by name only.
- `COPILOT_ALLOW_ALL`: NOT used. Note the trap it contains:
  exactly `"true"` additionally trusts the working directory
  (loading its skills, plugins, MCP servers, and hooks, including
  shell-command hooks); other truthy spellings only auto-approve
  tools. The flag form avoids this ambiguity.
- `COPILOT_HOME`: config/state dir (default `~/.copilot`). On CI
  it is the runner's ephemeral home; nothing persists.
- `COPILOT_PROVIDER_*` (BYOK): bypasses GitHub auth entirely.
  Out of scope for this harness (see README).

## What this design cannot measure (say so in every report)

- Interactive approval dialogs: -p has none, and --no-ask-user
  removes the ask_user tool. A deny-rule verdict is not evidence
  about how the interactive CLI prompts, and must never be
  reported as such.
- Model judgment vs rule firing: if the agent refuses in prose
  without invoking a tool, the runner records `decision_kind:
  model-refusal`, distinct from `deny-rule`. Both count toward
  the smoke PASS (the delete did not happen with a recorded
  decision), but only `deny-rule` is a permission-system signal.
- Wrapper invocations (`bash -c`, `sudo`, script files) and
  non-shell deletion paths (write-tool truncation, MCP tools):
  separate scenarios, not smoke claims.
- Sandbox status: no sandbox flag is used; the smoke runs
  un-sandboxed in a scratch tree on an ephemeral runner. Sandbox
  status is "not started", never a pass.
