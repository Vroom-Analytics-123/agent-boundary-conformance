# Live-pinned approval configs (2026-10-22)

Exact approval-config contents pinned by `docs/approval-effect-protocol.md`
§4. These files are the ONLY configs under which a witnessed approval
counts. They are committed as text so the protocol's lock is
byte-verifiable; the witness driver (`tools/approval_witness.py`) loads them
from here.

| File | Harness | What it pins |
|---|---|---|
| `codex.toml` | Codex 0.149.0 | `approval_policy=never`, `sandbox_mode=workspace-write` (equivalent to the live invocation's `-c approval_policy=never -s workspace-write`) |
| `claude-code.settings.json` | Claude Code 2.1.307 | `permissions.defaultMode=default` + the corpus-analogous allow/ask/deny set (deny→ask→allow, first match wins) |
| `opencode.approval.json` | OpenCode 1.19.3 (1.x) | 1.x `permission` object: `"*": "ask"` catch-all FIRST, then corpus-analogous patterns (last-match-wins; key order is the precedence operator) |
| `amp.settings.json` | Amp 0.0.1792680614-g8973a3 | `amp.permissions`: allow `git status*`/`ls*`; ask `deployctl release*`; reject `rm -rf *`/`rm --recursive --force *` (first-match-wins, user rules precede built-ins) |

Notes:
- The OpenCode fixture here DIFFERS deliberately from
  `adapters/opencode/policy/opencode.json`: the adapter fixture omits the
  `"*": "ask"` catch-all so no-match corpus cases evaluate the TRUE
  no-pattern path (Decision layer). The LIVE pin keeps the catch-all first —
  the config a real contained run would use.
- The Amp fixture is the wave's corpus-analogous policy from
  `docs/live-test/PREREGISTRATION.md` §5, not the spike's 41-case
  corpus policy (`evidence/amp-spike-2026-10-22/corpus-policy.json`).
- All configs are validated by `tools/approval_config_check.py`
  (schema checks, REPRO) and used by `tools/approval_witness.py`.
