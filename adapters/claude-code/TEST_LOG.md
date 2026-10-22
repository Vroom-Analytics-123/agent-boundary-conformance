# Claude Code wave — TEST_LOG (2026-10-22)

## 1. Version under test

- Installed: `@anthropic-ai/claude-code@2.1.307` — the manifest pin
  (`adapters/claude-code.manifest.json`, spike 2026-10-21).
- Install route (official, no login): npm registry, workspace-local scratch
  dir (NOT the repo):
  ```
  mkdir -p /tmp/cc-scratch && cd /tmp/cc-scratch
  npm pack @anthropic-ai/claude-code@2.1.307        # tarball verified
  npm init -y && npm install @anthropic-ai/claude-code@2.1.307 --no-audit --no-fund
  ```
- Tarball integrity (npm registry): `sha512-/G+XTieqaNEpug8R7iQSgEvWYO7nRsxs3Hm7f0bSHboVn1KYr5rBgUFwXnAqmbFEtVek+qbl5n/xdX5eezKNGA==`
- `claude --version` -> `2.1.307 (Claude Code)` (offline, no session, no login).
- Registry metadata (npm view): 2.1.307 published `2026-10-21T20:47:18.383Z`;
  latest at run time was 2.1.308 (published `2026-10-22T04:19:48.902Z`).
- Why 2.1.307 and not latest: the manifest spike (docs retrieved 2026-10-21)
  was pinned to 2.1.307; 2.1.307 installs cleanly without login, so the
  re-run at the pinned version keeps the comparison consistent. Recorded as
  `version_under_test` in results.json.
- Scratch dir `/tmp/cc-scratch` was ephemeral and has been removed; the
  install left no trace in the repo and no state on the machine beyond /tmp.

## 2. Spike (a) re-run: native offline decision oracle?

Read-only inspection only (`claude --help`, `claude --version`,
`claude auto-mode --help`, `claude doctor --help`). No session launched,
no repo touched, no login performed.

Subcommand list at 2.1.307: agents, attach, auth, auto-mode, doctor,
gateway, import, install, logs, mcp, plugin(s), purge, respawn, rm,
setup-token, stop/kill, ultrareview, update/upgrade.

CONFIRMED: still NO native offline decision oracle. No check / evaluate /
dry-run subcommand exists. `doctor` is install/settings diagnostics;
`auto-mode config`/`defaults` print the classifier's effective RULES as JSON
(config inspection, not a per-command oracle) — consistent with the
2026-10-21 spike. Route taken: (b) T2 config evaluation, labelled
"T2-evaluation (never interrogated)".

## 3. Engine unit tests

`python3 test_engine.py` (plain assert runner, adapters/claude-code/):

- 85 tests, 85 pass, 0 fail.
- Coverage: every row of the official docs' Bash wildcard table
  (https://code.claude.com/docs/en/permissions — "Wildcard patterns",
  "Match all uses of a tool", "Use specifiers for fine-grained control",
  "What a Bash rule doesn't match", "Compound commands", "Wrappers";
  each test cites the docs section in test_engine.py), the `:*` suffix
  equivalence, bare-`Bash`/`Bash(*)` equivalence, wrapper stripping
  (incl. `command -v` query-form and flagged-xargs negatives), env-assignment
  stripping asymmetry (deny/ask past any assignment; allow past NODE_ENV
  only), compound splitting (&&, ||, ;, |, quote-aware), nested
  `$(...)`/backtick extraction for deny/ask (docs' `echo "$(git clean -f)"`
  example), precedence probes in both orders (deny>ask>allow, specificity
  irrelevant), the no-match -> unknown default, and the built-in read-only
  set (incl. `find -delete` and unquoted-glob negatives).

## 4. Corpus evaluation

`python3 run_corpus.py` (adapters/claude-code/):

- 41 corpus fixtures evaluated locally: public 21 + held-out 20.
- Protected-asset family: 6 fixtures (public shard) + supplementary tree-idiom probe.
- Command string = `" ".join(argv)` (the command text as written).
- Fixture->policy mapping: `fixtures/policies/default.rules` ->
  `policy/settings.json`; `fixtures/policies/protected_records.rules` ->
  `policy/protected.json`; `evidence/day1-baseline-2026-10-21/prec_{a..f}.rules`
  -> `policy/prec_{a..f}.json`.
- Codex T1 native baseline for the divergence comparison: latest reruns
  `evidence/reruns/rerun-20261022T160502Z.json` (default+prec policies) and
  `evidence/reruns/rerun-20261022T160536Z.json` (protected policy).
- Determinism: two consecutive runs are byte-identical after normalizing
  `generated_utc` (wall clock only).
- Results: public expected_match 15/21; protected 6/6; 13 divergences from
  Codex T1 native (see results.json; headline list in the wave report).
- Held-out shard: evaluated locally, per-case detail ONLY in the gitignored
  `results_heldout.local.json`; `results.json` carries aggregate counts +
  shard sha256 `b0cf883466770f01c0083ba55eb129c17dc558f6d3858c269408c46ca12d7f3c`
  (from fixtures/corpus_manifest.json) per fixtures/HELDOUT_POLICY.md.
- Held-out aggregate decisions: allow 2, prompt 2, forbidden 6, unknown 10.

## 5. Git hygiene

- `adapters/claude-code/results_heldout.local.json` verified git-ignored
  (pattern appended to repo `.gitignore` by this wave; `git check-ignore`
  confirms). Nothing committed or pushed by this wave.
