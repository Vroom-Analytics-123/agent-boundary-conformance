# FinePrint free check — GitHub Action wiring guide

Plain words first. A **harness** is the coding agent you use (Codex,
Claude Code, Muse Code). A **policy** is the file of rules you wrote
for it. A **check** asks the harness's own policy checker what it
decides for each of 16 built-in rules (Catalogue v1) and tells you
which ones held and which ones broke. **BLOCKED** means a rule broke.

## Add it to your repo (two steps, no config)

1. Copy `.github/workflows/fineprint-check.yml` from this repo into
   your repo at the same path. (The Action it calls is defined in
   `action.yml` at this repo's root.)
2. Push. That is all.

The first job in that file calls the Action with no settings at all.
The Action finds your harness on its own: it looks for
`fineprint.rules` (Codex), `fineprint.settings.json` (Claude Code),
or `.claude/settings.json` (Claude Code) in your repo. If you do not
have any of those yet, run this once on your machine first:

```bash
fineprint init
fineprint check
```

`init` writes starter files. `check` runs the check. Both are one
command with no settings. See the README quickstart.

## What you will see

- **Actions tab:** green means no rule broke. Red means BLOCKED — a
  rule broke, and the failing step names it.
- **Pull request:** a comment titled "FinePrint check" with the
  counts (satisfied / not satisfied / unresolved).
- **Artifacts on the run:** a `fineprint-evidence` download with
  `bundle.json` (the sealed evidence), `scorecard.json`, and
  `scorecard.html` (open it in a browser for the readable table).

## When it is red

1. Open the failed run and read the step output. It names the broken
   rule, e.g. `BLOCKED: 1 rule(s) broken: FP-001`.
2. Open `scorecard.html` from the artifact. Find the rule. It shows
   what the policy decided and what the rule expected.
3. Fix your policy file so the rule is forbidden or asks first, then
   push again. A green run after a red one is the fix working.

`UNRESOLVED` is not red. It means the policy does not answer that
probe — the check reports it instead of hiding it.

## Pinning a harness and policy (optional)

The second job in the example workflow shows the explicit form:

```yaml
- uses: Vroom-Analytics-123/agent-boundary-conformance@main
  with:
    harness: codex
    policy: fixtures/policies/default.rules
```

In your repo, use the `@main` reference. Inside this repo the example
uses `./` so this repo's own CI tests the local Action.

## Codex needs the oracle binary (Claude Code does not)

The Codex check asks the real Codex policy checker, which lives in a
247 MB binary that GitHub will not store (files over 100 MB are
rejected). The example workflow restores it with the repo's documented
recipe — see `tools/vendor/codex/0.149.0/VENDORED.md` — and checks its
SHA-256 before use. Never run oracle work on an unpinned binary.

Claude Code needs nothing: its check is pure Python, no binary, no
key, no network.

## Muse Code

Muse Code has no offline decision oracle, so a check reports
UNMEASURED instead of a verdict (exit 3, bundle records the gap).
Live measurement for Muse Code runs through the `musecode-smoke`
workflow in this repo: it needs your own `MUSE_HEADLESS_KEY` secret
(repo Settings → Secrets and variables → Actions) and runs on a
GitHub-hosted runner. See `INTEGRATION.md` and
`musecode-smoke/README.md`. Never paste a key into a workflow file.

## No secrets for the default check

The default check needs no secrets and makes no network calls to any
harness company. The only network in the Codex job is the public npm
download of the Codex binary itself (the documented restore recipe).

## Inputs (all optional)

| Input | What it does | Default |
|---|---|---|
| `harness` | `codex`, `claude-code`, or `muse-code` | auto-detect |
| `policy` | policy file to check | auto-detect |
| `only` | e.g. `FP-001,FP-016` — check only these rules | all 16 |
| `baseline` | path to a previous `bundle.json` — a regression fails the build | none |
| `rules` | path to a DIY rules file (`fineprint init --rules`) | none |
| `out` | directory the evidence bundle is written to | `fineprint-evidence` |

Empty inputs count as unset: the CLI treats an empty value as
"auto-detect". The check step never swallows exit 2 (BLOCKED) — a
broken rule fails the build on purpose.
