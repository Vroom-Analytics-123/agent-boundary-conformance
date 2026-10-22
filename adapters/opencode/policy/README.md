# OpenCode 1.x policy fixtures — translation notes

Pinned semantics: **opencode 1.x `permission` object** (adapter pins 1.x;
the 1.x/2.x schema break is load-bearing — 2.x uses an ordered
`permissions` list of `{action, resource, effect}` and needs a separate pass).

Source of the translation: `security/invariants.yaml` (INV-001..INV-005, via
the rules-layer encoding in `fixtures/policies/default.rules`) and the
protected-asset family (`fixtures/policies/protected_records.rules`).

## Translation rule (applied mechanically, order preserved)

`prefix_rule(pattern=[t1, ..., tn], decision=d)` becomes one `shell` pattern
entry:

    "t1 t2 ... tn*" : verb

with `allow -> allow`, `prompt -> ask`, `forbidden -> deny`.
File order of the `.rules` source is preserved as JSON key order in the
`shell` object — under 1.x **last matching rule wins**, so key order is the
precedence operator.

- `opencode.json` — translation of `fixtures/policies/default.rules`
  (current version, incl. the Day-5 `[rm, --recursive, --force]` rule).
- `policy.order-swapped.json` — the exact reverse key order of `opencode.json`.
- `protected-records.json` — translation of `fixtures/policies/protected_records.rules`.
- `protected-records.order-swapped.json` — exact reverse key order.

## Explicit normalization assumption (T2 ceiling)

The corpus fixtures carry `argv` (token lists). OpenCode's `shell` tool
matches "parsed commands", but the vendor does not document the
parsing/normalization step (`adapters/opencode.manifest.json`, open question).
The engine's explicit assumption: the evaluated command string is
`" ".join(argv)` — single-space join, no quoting, no shell re-parsing.
`evaluate.py::normalize_command` implements exactly this. Any vendor
normalization (quoting, `~` expansion, env interpolation) is UNMEASURED and
would change matches.

## Lossy translations (ceilings, all recorded per case)

1. **Token-prefix vs string-prefix.** Codex `prefix_rule` matches argv TOKEN
   prefixes; OpenCode patterns match the whole command STRING. The same
   developer intent behaves differently: `"rm -rf /records/health*"` matches
   `rm -rf /records/health/db.sqlite` (a subpath), where the token-prefix
   rule does not. Measured: PA-02 diverges (forbidden vs unknown). This is a
   genuine semantics difference, not a bug in either side.
2. **`*` over-match.** `*` matches zero or more of ANY character, so
   `"rm -rf*"` also matches `rm -rfx`. The token-prefix original would not.
   No corpus fixture exercises this; it is a documented over-approximation.
3. **No host-executable resolution layer.** Fixtures with
   `resolve_host_executables: true` (F-13R, F-14R, F-14bR, F-13d) are evaluated
   on the LITERAL command string — OpenCode has no documented equivalent of
   Codex's resolution layer. Their divergences are layer-coverage gaps, not
   verdict-semantics differences.
4. **No catch-all in the baseline policy — deliberate.** The docs' common
   pattern puts `"*": "ask"` first as a catch-all. It is omitted here so that
   no-match corpus cases (F-05, F-07, ...) evaluate the TRUE no-pattern path;
   the framework serializes no-match as `unknown` with layer attribution,
   never as allow (INV-005). The catch-all position effect is covered in
   `test_engine.py` instead (doc's own worked example, both orders).
5. **Agent merge mechanics are an inference.** The vendor doc says only
   "Agent permissions are merged with the global config, and agent rules take
   precedence" (opencode.ai/docs/permissions, § per-agent override). The engine
   implements: per tool key, a verb replaces; a pattern-object is appended
   AFTER the global patterns so last-match-wins gives the agent precedence.
   Tested against the doc's `build`-agent worked example in `test_engine.py`.
6. **Runtime-only layers are out of scope:** `--auto` flag (ask->allow at
   runtime, deny still enforced), session-state `always` approvals, `doom_loop`
   repetition detection, `external_directory` path guards. The engine evaluates
   the static permission object only.
