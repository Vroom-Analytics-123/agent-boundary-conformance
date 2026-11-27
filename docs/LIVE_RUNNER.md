# Live runner framework

One CLI, per-harness driver plugins, one record schema, proxy
lifecycle, cost logging, and Merkle sealing in one command. Built
from the recommendations in `docs/live-runs-audit-2026-11-07.md`
(on branch `feature/attribution-block-vs-not-attempted`): the Nov 4
runners are NOT rewritten — the framework is new code, and
migration is one harness at a time, using the sealed Nov 4 bundles
as regression oracles.

## First verdict: one command

```sh
python3 tools/live_run.py copilot-cli
python3 tools/live_run.py cursor
```

That is the whole interface for a first run. Everything else —
repeats, scenario set, output dir, proxy, sealing — comes from the
repo-shipped manifest (`adapters/<harness>.live.yaml`) and defaults.
No config file to write, no flags to learn first.

## Design

### Simplicity bar (Anish, Nov 7)

The free tier must be usable by the most junior dev, or even a
non-dev working with a harness — point-and-click or one simple
instruction, one command, zero config for a first verdict. The CLI
holds that bar at its default: naming the harness is the only thing
a first run asks. The explicit forms exist for scripts and
operators who want to say more, not as a toll on the first verdict:

```sh
python3 tools/live_run.py run copilot-cli --repeats 2 --sign
python3 tools/live_run.py list-harnesses
python3 tools/live_run.py status --harness copilot-cli
python3 tools/live_run.py verify --bundle <bundle.json>
python3 tools/live_run.py compare --baseline <sealed.json> --fresh <new.json>
```

A mistyped harness fails kindly (`error: no live manifest ...` +
a hint to `list-harnesses`), never with a traceback. A run whose
environment is not ready (binary or secret missing) still produces
a sealed bundle of `MISSING_AUTH` records — a missing-auth run is
evidence, not a crash — and the CLI is never invoked without its
auth.

### Records

One record per scenario variant (`schemas/live_run_record.v1.schema.json`),
with `repeats[]` inside (default 2, the Nov 4 live standard: 24
variants x 2). The top-level verdict is repeat 1 (primary). The
bundle tally per variant is its WORST repeat (harm in any repeat
marks the cell "executed"); `harm_total` counts cells with harm in
any repeat. Cost is logged per repeat (`tokens_in`, `tokens_out`,
`spend_usd`, `note`); the Nov 4 standard is untracked spend
(`spend_usd: null, note: "untracked"`) — a real cost needs a real
metering source, not a guess.

### Attribution

Non-attempts are classified per repeat with the vocabulary of
`tools/attribution.py`: `denied_by_rule` / `not_attempted` /
`no_decision`. The live classifier (`attribute_live_cell`) maps live
observations (`decision_kind` + harm) onto that vocabulary; the
check-run classifier (`attribute_non_attempt`) maps
(`actual_decision`, `observed_effect`). One module, one vocabulary,
two record shapes — the former duplicate `tools/live_attribution.py`
was reconciled into `tools/attribution.py` and deleted on
`demo/live-harness` (Nov 8, 2026). A deny-rule attribution never
invents a rule id: the id is the driver's cited rule, or null. Harm
executed is never a non-attempt; benign cells carry no attribution.

### Sealing and compare

Every run seals its bundle with the same Merkle helpers as the
sealed bundles (`tools/schemas_v1.py`: `leaf_hash_for_finding` /
`build_merkle`) and self-verifies before writing
(`verify_live_bundle` re-derives tallies, `harm_total`,
`cell_count`, and the Merkle root). `--sign` adds a detached
Ed25519 signature via `tools/bundle_signing.py` and fails loudly
when no signing key exists.

`compare` is the regression oracle: it normalizes both the sealed
`live-bundle.v1` shape (per-(variant, repeat) rows) and the new
`live-run-record.v1` shape (per-variant records with `repeats[]`)
into (variant, repeat) -> verdict and reports regressions (harm
newly executed, or a decision newly lost), improvements, and flips.
Exit code 1 when regressions > 0. The sealed bundles under
`evidence/` are never modified; the runner refuses to overwrite an
existing output dir.

### Drivers

A driver is one module in `tools/live_drivers/` exposing a `Driver`
class (`tools/live_drivers/base.py`): `check_environment`,
`cells`, `run_cell`. The framework owns everything else: CLI,
manifests, proxy lifecycle, repeats, attribution, cost, sealing,
compare. Implemented drivers:

- **copilot** (`tools/live_drivers/copilot.py`): reuses the sealed
  Nov 4 full-matrix runner (`framework/scorecard/copilot-full-v1/
  runners/full_runner.py`: `FULL_TASKS` + `run_cell`) without
  rewriting it, and adds the one thing the legacy record lacks —
  the model actually observed, parsed per cell from the CLI's JSONL
  stdout (`model` fields, `modelCacheState` modelId, `modelMetrics`
  keys). Model unpinned by design; exactly one distinct model is
  observed, zero or several is "unobserved".
- **cursor** (`tools/live_drivers/cursor.py`): reuses the same
  legacy runner's fixtures and harm evaluation
  (`setup_scratch` / `snapshot` / `canary_for` / `start_sink` /
  `setup_git_diverged` / `write_kubectl_stub` / `write_deploy_script`
  / `write_npm_package` / `eval_harm` and the verdict markers)
  with a Cursor-specific invocation (`agent -p <prompt> --force
  --output-format stream-json`) and output parsing. Same 24 cells,
  same prompts, same harm kinds as the Copilot matrix, so the two
  harnesses are comparable cell-for-cell. No deny rule is
  configured this round (the `.cursor/cli.json` deny syntax is not
  established from Cursor's docs); denial wording is a model
  refusal, never a deny-rule. Model unpinned by design; observed
  per cell from the stream-json events.

Adding a driver: copy one of the above, implement the three
methods, add its manifest, add replay tests with a fake binary
(see `tests/test_live_drivers_copilot.py` /
`tests/test_live_drivers_cursor.py`), and wire a dispatch workflow.

### Proxies

`tools/live_proxy.py` manages proxy lifecycle (start, TCP/HTTP
health check, stop) and ships the generic OpenAI-compatible proxy
server (`live_proxy.py serve --port P --arm cheaper|meta --model M`)
for model-agnostic drivers. The per-harness proxies that predate
the framework are vendored verbatim under `tools/proxies/` with
provenance headers: `claude_proxy.py` (Anthropic pass-through,
fixed port 8898, TCP health only), `gemini_translator.py`
(Gemini→OpenAI translator, port 8897, `GET /`), `omnigent_proxy.py`
(OpenAI-compatible + `/responses`, port 8893, `GET /health`).
The OpenCode proxy is NOT vendored: it is the same generic
OpenAI-compatible pattern as `live_proxy.py serve`, which the
opencode manifest points at — it must be validated against a real
opencode run before it replaces the local one.

### Manifests

`adapters/<harness>.live.yaml`: binary pin + install recipe, auth
method, mandatory observed model pin, sandbox mode, proxy, workflow,
scenario set, repeats, sealed-bundle evidence (Merkle root). A pin
is either concrete (from a sealed bundle) or `UNKNOWN` with a
`unknown_settled_by` note. Never guess a pin. 16 manifests: the 14
live harnesses + `cursor` (live since 2026-11-08) + `pi`
(not applicable by design).

### Auth

See `docs/AUTH_INVENTORY.md` — secret/account names only, never
values.

## Pilots

### Copilot (first harness on the framework)

```sh
# Local fail-closed proof (no token): 24 MISSING_AUTH cells, sealed.
python3 tools/live_run.py copilot-cli --out /tmp/copilot-missing-auth-v1

# Real pilot (post-merge, on Actions — the workflow is registered
# from the default branch):
#   dispatch .github/workflows/harness-live-copilot.yml
#   out: framework/scorecard/copilot-pilot-v1/
# Then:
python3 tools/live_run.py verify --bundle framework/scorecard/copilot-pilot-v1/bundle.json
python3 tools/live_run.py compare \
  --baseline evidence/live-2026-11-04/copilot-full/bundle.json \
  --fresh framework/scorecard/copilot-pilot-v1/bundle.json
```

Pilot evidence achievable without the live secret (all done on
this branch): fake-binary replay tests using real recorded stdout
(`tests/test_live_drivers_copilot.py`), the MISSING_AUTH
end-to-end run above, and the compare tool proven against the
sealed bundle (identity = 0 flips; mutated copy = 1 regression +
1 improvement, exit 1).

### Cursor (second harness; key landed 2026-11-08)

```sh
# Local fail-closed proof (no binary, no token): 24 MISSING_AUTH cells.
python3 tools/live_run.py cursor --out /tmp/cursor-missing-auth-v1
```

Real pilot: dispatch does NOT work for a workflow that exists only
on a branch — GitHub 404s the dispatch (and the workflow-by-name
lookup) until the workflow lands on main, which is frozen for
judging until the Nov 9 ceremony. So
`.github/workflows/harness-live-cursor.yml` ALSO fires on a push
that touches only that file, scoped to this branch: the push that
adds the trigger runs the pilot once, and the workflow's own
record-commit push (which touches only `cursor-pilot-v1/`) does
NOT re-trigger it. After the post-ceremony merge, dispatch works
from main and the push trigger should be removed. Pilot output:
`framework/scorecard/cursor-pilot-v1/`. Then verify the bundle.
There is NO sealed baseline for Cursor, so no compare step — the
pilot run BECOMES the baseline.

```sh
python3 tools/live_run.py verify --bundle framework/scorecard/cursor-pilot-v1/bundle.json
```

## Tests

```sh
python3 -m pytest tests/ -q
```

185 tests + 136 subtests (Nov 7): CLI parsing (incl. the
one-command form), driver loading, record schema, sealing +
tamper detection, compare (incl. the sealed bundle), proxy
lifecycle + vendored-proxy smoke tests from the repo path,
manifest completeness, Copilot + Cursor fake-binary replays.

## What remains

- Drivers for the other 12 live harnesses (amp, openclaw,
  claude-code, muse-code, hermes, omnigent, gemini-cli, codex,
  opencode, goose, strands, langgraph, crewai) — manifests exist;
  drivers do not. One harness at a time, sealed bundle as oracle.
- Cursor deny rule: settle the `.cursor/cli.json` deny syntax from
  Cursor's docs, configure it, and record it in the driver +
  manifest (today: no rule; denial wording is a model refusal).
- Cursor binary pin: `UNKNOWN` until the dispatch run reports
  `agent --version`.
- Pi: no driver by design (vendor-confirmed no permission system).
- Merge this branch after the Nov 9 ceremony (main is frozen for
  judging until then); the dispatch workflows only register from
  the default branch.
