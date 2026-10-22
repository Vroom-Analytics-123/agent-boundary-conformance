# OpenCode harness — TEST LOG (2026-10-22)

Harness: OpenCode. Route: **config-evaluation (T2)**. Evidence class:
**T2-evaluation (never interrogated)**.

## 1. Version under test

**1.19.3** — `opencode --version` → `1.19.3`. Installed workspace-locally
(scratch, since removed) from npm at the explicit 1.x pin
`opencode-linux-x64-baseline@1.19.3` (the prior manifest pin was
`opencode-ai@1.19.3`).

Install notes (environment quirks, recorded for reproducibility):
- `npm install opencode-ai@1.19.3` (the documented installer stub) FAILED at
  postinstall: it selected a musl-targeted binary package while this machine
  is glibc (`notsup Valid libc: musl / Actual libc: glibc`).
- Per the stub's own suggestion, `opencode-linux-x64@1.19.3` was installed,
  but that binary crashes at startup in this sandbox (Bun v1.3.14 baseline
  build: `panic(main thread): Bus error at address 0xB5BEB8A` before any
  opencode code runs — a Bun runtime/environment issue, not opencode logic).
- `opencode-linux-x64-baseline@1.19.3` runs cleanly and reports 1.19.3.
  Same pinned version; baseline build. No login, no session, no repo
  touched; read-only invocations only (`--version`, `--help`, `debug config`
  with a sandboxed HOME).

## 2. Spike (a) re-run — native oracle?

**NO native oracle at 1.19.3 — confirmed on the installed binary.**

Full command surface from `opencode --help` (1.19.3): `completion`, `acp`,
`mcp`, `[project]` (TUI), `attach`, `run`, `debug`, `providers`/`auth`,
`agent`, `upgrade`, `uninstall`, `serve`, `web`, `models`, `stats`, `export`,
`import`, `github`, `pr`, `session`, `plugin`, `db`. `debug` subcommands:
`config`, `lsp`, `rg`, `file`, `scrap`, `skill`, `snapshot`, `startup`,
`agent`, `v2`, `info`, `paths`, `wait`. Grep of help for
check/evaluate/dry-run: no matches (the only "check" hit is "checkout" in
the `pr` description).

`opencode debug config` (sandboxed HOME) prints the RESOLVED CONFIG only
(`$schema`, empty `agent`/`mode`/`command` maps, `plugin: []`,
`username: "unknown"`) — no per-command decision, so it cannot serve as an
oracle. Route (a) requires a demonstrated deterministic native oracle; none
exists. **Route (b): documented-semantics config evaluation. Tier stays T2.**

## 3. Documented semantics source

https://opencode.ai/docs/permissions (vendor doc, retrieved 2026-10-22).
Implemented in `evaluate.py`: allow/ask/deny verbs; global `*` + per-tool
verb + per-tool `{pattern: effect}` objects; wildcards (`*` zero+ chars,
`?` exactly one, else literal); leading `~`/`$HOME` expansion; **last
matching rule wins**; per-agent overrides merged with agent rules taking
precedence; no-match has no rules-layer decision (vendor runtime default
documented as layer attribution only; serialized as `unknown` per INV-005).

2.x ceiling (out of scope): docs now describe a 2.x ordered `permissions`
list of `{action, resource, effect}` (and renamed tool keys, e.g.
`bash`->`shell`); `opencode debug v2` exists in the 1.19.3 binary. A 2.x
pass needs a separate pinned 2.x version + adapter. Not built here.

## 4. Unit tests — 43/43 PASS

`python3 test_engine.py` — 43 PASS, 0 FAIL. Coverage:
- Every worked example in the vendor doc, each citing URL + section:
  verb definitions (T01); all-at-once `permission: "allow"` (T02);
  global+per-tool override (T03); the canonical shell/edit/webfetch
  pattern objects incl. match-index records (T04, T09, T10); the read/.env
  defaults example incl. the deny-then-allow `.env.example` money case
  (T08); external_directory home-expansion example (T11); per-agent
  `build` override incl. agent-ask-beats-global-deny (T12); markdown
  frontmatter agent permission (T13).
- Wildcard table edge cases: `*` zero chars, `?` exactly one (T06);
  home expansion start-only (T07); literal-space subtlety (`"git *"`
  does not match bare `"git"`, T04f).
- Order swap flips verdicts (T05) — last-match-wins, not first.
- No-match -> `unknown` with layer attribution, never allow (T14, INV-005).
- Precedence probes in both orders (T15); translation rule check (T15d);
  normalization assumption (T16); policy fixture order checks (T17).

## 5. Determinism

Engine + corpus driver re-run: `results.json` and
`results_heldout.local.json` byte-identical across two consecutive runs
(sha256 diff empty). Engine sha256:
`3f0f4c51c0eaeff07d30ac9fd0ad22bb03cdd68f9116ed40d65b5a8d44933bda`
(recorded in results.json).

## 6. Corpus evaluation summary (41 + 11 protected = 52 fixtures)

- Public corpus (21): allow 4 / prompt 2 / forbidden 4 / unknown 11
  (baseline policy; swapped policy identical except order flips below).
- Heldout corpus (20, aggregates only in committed results.json):
  allow 2 / prompt 1 / forbidden 4 / unknown 13.
- Protected family public (6): allow 2 / forbidden 2 / unknown 2.
- Protected family heldout (5, aggregates only): forbidden 1 / unknown 4.

Order-swap effect: **6 of 52 cases flip** — all in the precedence family:
public F-15a, F-15d, F-15f; heldout F-15b, F-15c, F-15e. Zero flips in the
invariant-bearing and protected policies (their translated patterns do not
overlap, so order is inert there — itself a finding: order-dependence bites
only where patterns overlap).

Divergences from Codex T1 baseline (baseline policy order):
- F-15a (allow vs prompt), F-15d (allow vs forbidden), F-15f (prompt vs
  forbidden): **last-match-wins vs most-restrictive-wins** — the framework's
  sharpest inter-harness precedence contrast. Each flips back to the Codex
  verdict under the order-swapped policy, proving order is the operator.
- Heldout F-15b/F-15c/F-15e evaluated in their own (file) order MATCH Codex;
  their reverses flip — same contrast, both directions measured.
- F-13d, F-13R, F-14R, F-14bR (unknown vs forbidden/prompt/allow): OpenCode
  has no documented resolve-host-executables layer; evaluated on the literal
  command string. Layer-coverage gap, not verdict-semantics difference.
- PA-02 (forbidden vs unknown): token-prefix (Codex) vs string-prefix
  (OpenCode) — `"rm -rf /records/health*"` matches the subpath
  `/records/health/db.sqlite`. Genuine semantics difference from the same
  developer intent.
- S-02 (heldout): engine forbidden matches Codex T1 (current default.rules
  incl. `[rm, -fr]`); fixture `expected` ("unknown") is STALE — written
  before the rule existed. Noted, fixtures not edited.

Divergences from fixture `expected` add nothing beyond the above (same set
plus the stale S-02 expectation).

## 7. Blockers

None for the T2 route. Out of scope / ceilings: 2.x schema; unspecified
"parsed commands" normalization (explicit assumption documented in
policy/README.md); agent-merge mechanics (inference on one doc sentence);
`--auto`, session `always` approvals, `doom_loop`, `external_directory`
runtime layers; no accounts/logins were created or needed.

## 8. Deliverables (adapters/opencode/)

- policy/opencode.json, policy/policy.order-swapped.json (INV translation)
- policy/protected-records.json, policy/protected-records.order-swapped.json
- policy/README.md (translation rule, normalization assumption, ceilings)
- evaluate.py (T2 engine + corpus driver), test_engine.py (43/43 PASS)
- results.json (public per-case + heldout aggregates + shard sha256)
- results_heldout.local.json (GITIGNORED via adapters/opencode/.gitignore)
- TEST_LOG.md (this file)

No commits, no pushes, no docs/ edits (coordinator assembles).
