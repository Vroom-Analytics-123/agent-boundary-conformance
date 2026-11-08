# FinePrint integration — wire it into a repo's dev loop

This guide is for a junior developer, or a person working with a
coding agent who is not a developer at all. No assumed knowledge:
every word that matters is defined where it first appears.

**FinePrint** checks whether a coding agent follows its own rules.
A **harness** is the coding agent you use — Codex, Claude Code, or
Muse Code. A **policy** is the file of rules you wrote for that
agent (for example: "never delete without asking"). A **check** asks
the harness's own policy checker what it decides for each of 16
built-in rules (Catalogue v1) and tells you which ones held and
which ones broke. **BLOCKED** means a rule broke. A **bundle** is the
sealed evidence file the check writes — proof of what was measured,
on what date, with which policy.

The free tier works in three steps, in this order:

1. **Check (worry).** Run the check on your machine. It shows, with
   measured evidence, that the guard fails — which rules break, on
   what date, with the sealed bundle to prove it. That is the
   five-minute path below.
2. **Action (peace of mind).** Add one workflow file to your repo and
   the check runs on every pull request: red means a rule broke,
   green means it held, and the evidence bundle is downloadable from
   the run. No terminal needed — see `docs/FREE_CHECK_ACTION.md`.
3. **Wall (the bouncer).** Run the agent itself inside the wall
   (`fineprint gate run -- ...`). The wall is the thing that actually
   stops the harm: the agent can only see the allowed scope and can
   only reach allowlisted hosts. See "The gate" below and
   `docs/FREE_GATE.md`.

If you never open a terminal, step 2 is your surface: the GitHub
Action. Add one file in the GitHub web UI, read red/green on the
pull request. The CLI (steps 1 and 3) is one command for engineers.
A desktop one-click installer is a later phase — it is not in this
branch.

## The five-minute path (one command, no config)

You need Python 3.10 or newer and a copy of this repo. Clone it,
then:

```bash
./fineprint check
```

That is the whole first run. No flags, no config file, no account,
no key. The command finds your harness on its own: it looks for
`fineprint.rules` (Codex), `fineprint.settings.json` (Claude Code),
or `.claude/settings.json` (Claude Code) in the current directory.
If it finds none of those, it tells you to run `fineprint init`
first (see below).

What you will see (a real run, Claude Code):

```
auto-detected: claude-code (found fineprint.settings.json in this directory)
bindings: the repo's recorded demo bindings (pass --bindings to use your own)
running the check (Paper Test: what the policy decides)...
adapter: claude-code (reconstructed) — engine ok: adapters/claude-code/evaluate.py (documented semantics, never interrogated)
pack: 16 invariants (core=16, domain=0, org=0)
wrote /home/hatch/workspace/scratch-integ/fineprint-evidence/check-20261108-003723/bundle.json (+ scorecard.json/html, bindings.json, composition.json)
bundle fineprint-check-20261108-003723-696304: status=valid pass=51 fail=14 not_run=0
intent: SATISFIED=1 NOT_SATISFIED=0 UNRESOLVED=13 NOT_APPLICABLE=2
bundle: /home/hatch/workspace/scratch-integ/fineprint-evidence/check-20261108-003723/bundle.json
smoke: live decision source answered; bundle verifies
PASS: no rule broken. intent: SATISFIED=1 UNRESOLVED=13 (UNRESOLVED = the policy does not answer that probe — reported, not hidden).
```

Reading that output, line by line:

- **auto-detected** — which harness it found, and which file told
  it. If this line names the wrong harness, you are in the wrong
  directory.
- **bindings** — the check needs values for placeholders like
  `<protected_path>` in the rules. By default it uses the repo's
  recorded demo bindings. That is fine for a first run; pass
  `--bindings` with your own file when the paths matter to you.
- **adapter** — the piece of the engine that talks to your harness.
  "vendor-confirmed" (Codex) means the checker is the vendor's own
  binary, pinned by SHA-256. "reconstructed" (Claude Code) means the
  checker was rebuilt from the harness's documented rules — it is an
  evaluation, not an interrogation of the harness.
- **pack: 16 invariants** — the 16 built-in rules, FP-001 to FP-016.
- **wrote .../bundle.json** — the sealed evidence, plus a readable
  scorecard (`scorecard.html` — open it in a browser).
- **status=valid** — the bundle's seal checks out. If it ever says
  anything else, the evidence is broken; do not trust it.
- **intent: SATISFIED=1 NOT_SATISFIED=0 UNRESOLVED=13** — 1 rule
  fully held, 0 broke, 13 the policy does not answer. **UNRESOLVED
  is not a failure.** It means the policy has no answer for that
  probe, and the check reports it instead of hiding it.
- **smoke** — after the Paper Test, the check re-runs one probe
  fresh through the real decision source and re-verifies the bundle.
  This proves the measurement is live, not a cached result. Skip it
  with `--no-smoke` if you are in a hurry.
- **PASS** — no rule broke. Exit code 0.

The Codex run looks the same, takes about 30 seconds (it starts the
real Codex policy checker), and needs the oracle binary restored
first — see "Codex needs the oracle binary" below. The Muse Code run
is different — see "Muse Code" below.

## If there is no harness config yet: `init`

```bash
fineprint init
```

One command, no flags. It writes starter files in the current
directory and tells you what it wrote:

```
fineprint init — scaffolding starter files in /home/hatch/workspace/scratch-integ:
  wrote fineprint-gate.json (free gate policy (this directory only))
  wrote fineprint.rules (Codex starter policy (forbids rm -rf, prompts on deploy, allows the benign read))
  wrote fineprint.settings.json (Claude Code starter settings)
  wrote fineprint-muse-code.json (Muse Code note (no local policy file exists))
  live measurement for Muse Code runs through the musecode-smoke workflow — see INTEGRATION.md
next: fineprint check
```

Then run `fineprint check`. That is the two-command flow: `init`,
then `check`.

- `fineprint init --harness codex` — only the Codex starter.
- `fineprint init --harness claude-code` — only the Claude Code
  starter.
- `fineprint init --harness muse-code` — only the Muse Code note.
- `fineprint init --gate` — only the gate policy file.
- `fineprint init --rules my-team.rules` — also scaffolds a DIY
  rules file (see "Your own rules" below).

## What BLOCKED looks like

Break a rule on purpose and see it. This policy allows `rm -rf`
(the thing FP-001 forbids):

```bash
printf 'prefix_rule(pattern=["git", "status"], decision="allow")\nprefix_rule(pattern=["rm", "-rf"], decision="allow")\n' > violating.rules
fineprint check --harness codex --policy violating.rules --only FP-001 --no-smoke
```

```
bundle fineprint-check-20261108-003736-795310: status=valid pass=8 fail=3 not_run=0
intent: SATISFIED=0 NOT_SATISFIED=1 UNRESOLVED=0 NOT_APPLICABLE=0
bundle: /home/hatch/workspace/scratch-integ/fineprint-evidence/check-20261108-003730/bundle.json
BLOCKED: 1 rule(s) broken: FP-001
What to do: open the scorecard (/home/hatch/workspace/scratch-integ/fineprint-evidence/check-20261108-003730/scorecard.html), find the broken rule, fix the policy file so the rule is forbidden or asks first, then run `fineprint check` again.
```

Exit code 2. That is the whole point: a broken rule fails the
build. In CI, the GitHub Action turns this into a red check on the
pull request (see `docs/FREE_CHECK_ACTION.md`).

**When it is red, do this:** open `scorecard.html` from the
evidence directory, find the broken rule, read what the policy
decided and what the rule expected, fix the policy file so the rule
is forbidden or asks first, and run the check again. A green run
after a red one is the fix working.

## Reading a bundle later

```bash
fineprint verify fineprint-evidence/check-20261108-003723/bundle.json
# bundle valid: fineprint-check-20261108-003723-696304 (65 findings, Merkle root 1bf4f4e89e67eca7…)

fineprint report fineprint-evidence/check-20261108-003723/bundle.json
# FinePrint report — bundle fineprint-check-20261108-003723-696304
# harness: claude-code (reconstructed)
# policy: /home/hatch/workspace/scratch-integ/fineprint.settings.json
# bundle: valid
#
# rule       name                             measured     intent
# FP-001     destructive_filesystem_delete    FAIL         UNRESOLVED
# FP-002     production_deploy_gate           FAIL         UNRESOLVED
```

Two columns matter. **measured** is whether the probes came back as
the rule expected (PASS/FAIL — FAIL here means the policy did not
answer, not that it allowed something bad). **intent** is whether
the rule holds: SATISFIED (held), NOT_SATISFIED (broke — this is
what BLOCKED means), UNRESOLVED (the policy does not answer that
probe), NOT_APPLICABLE (the rule does not apply to this harness).
Only NOT_SATISFIED fails the run.

`verify` re-checks the bundle's seal: it recomputes the Merkle root
over the findings and compares it with the root recorded in the
bundle. If a single finding was edited after sealing, verification
fails. Never edit a bundle by hand.

## The gate: one wrapper command (the bouncer)

The free gate has two parts: a **tripwire** (a fast pre-check of the
command and its arguments) and a **wall** (the command runs inside a
sandbox). One command, no config needed — the default is a
**protective denylist** (antivirus for agents): credential reads,
destructive deletes, exfiltration of protected files, and unapproved
deploys are blocked; normal work anywhere is allowed.

```bash
fineprint gate run -- cat notes.txt        # allows, exit 0
fineprint gate check --file ~/.ssh/id_rsa   # DENY, exit 2 (rule DENY-CRED-SSH)
fineprint gate run -- rm -rf notes.txt      # DENY, exit 2 (rule DENY-DELETE)
```

The tripwire deny looks like this (real output):

```
policy: built-in default (protective denylist — normal work anywhere is allowed, known-dangerous patterns are blocked; see `fineprint gate definitions`) — run `fineprint init --gate` to save it as fineprint-gate.json
GATE: DENY — file_read of a protected path: '/home/you/.ssh/id_rsa' resolves to '/home/you/.ssh/id_rsa' (rule DENY-CRED-SSH)
refusing to run: cat /home/you/.ssh/id_rsa
```

Exit code 2, and the command never ran. The rule id is printed,
and the same action will always be denied — deterministic, not a
judgment call.

The wall deny looks different: the command runs, then fails inside
because the file does not exist from its perspective. A script that
reads the SSH key — something the tripwire cannot see, because the
path is inside the script, not on the command line — fails with "No
such file or directory" and nothing leaks. That is the wall doing
its job.

Folder confinement is opt-in, not the default:

```bash
fineprint gate run --confine -- cat /etc/passwd   # DENY, exit 2 (rule CONFINE-PATH)
```

Save the policy as `fineprint-gate.json` with `fineprint init
--gate` and edit it (`mode`, `denied_paths`, `denied_hosts`,
`allowed_commands` to approve your own deploy script,
`allowed_paths` / `allowed_hosts` for confine mode). The denylist
itself is a signed, versioned pack — see `fineprint gate
definitions` (the update flow) and `fineprint gate log --log
audit.jsonl` (readable notifications of every blocked attempt).

**Read `docs/FREE_GATE.md` before trusting the gate.** It explains
how the wall works (the operating system's `unshare` tool, an
allowlist proxy for the network, a hash-chained audit log) and its
limits, stated plainly: the wall enforces scope (paths and hosts),
not intent — an agent misusing a file *inside* the allowed scope is
Check's job; the proxy controls egress only for tools that honor
proxy settings; the process list stays visible. The hardened gate
(process namespace, socket-level egress blocking) is the paid
product. The free gate never pretends to be it.

## Wiring it into a repo (for a coding agent)

If you are a coding agent pointed at a repo, do this:

1. `fineprint init` in the repo root, then `fineprint check`.
   Read the output. If it is PASS, you have a baseline bundle in
   `fineprint-evidence/`.
2. Add the check to CI: copy `.github/workflows/fineprint-check.yml`
   into the repo. No config needed for the default check. See
   `docs/FREE_CHECK_ACTION.md` for the wiring guide.
3. Add the gate to the commands your agent runs in CI or locally:
   `fineprint gate run -- <command>`. See `docs/FREE_GATE.md`.
4. Commit the policy files (`fineprint.rules` /
   `fineprint.settings.json` / `fineprint-gate.json`) and the
   workflow. Commit the evidence bundles too if the repo keeps them
   (this repo does, under `fineprint-evidence/`); otherwise let CI
   keep them as artifacts.
5. When a check goes red, fix the policy, not the test. A rule that
   fails because the policy allows something dangerous is the
   system working.

The MCP server in `mcp/` exposes the same checks to agents that
speak MCP — see `mcp/README.md`. It is the same engine; the CLI is
the simpler surface. Start with the CLI.

## Your own rules (DIY domain pack)

Catalogue v1 covers the common cases. For rules specific to your
team, write your own file and check against it alongside the
catalogue:

```bash
fineprint init --rules my-team.rules
```

That scaffolds one example entry (FP-LOCAL-001, marked UNMEASURED —
your rule has no measurement yet, and the check says so instead of
pretending otherwise). Edit the file, then:

```bash
fineprint check --rules my-team.rules
```

The rules file format is the repo's domain-pack format: a JSON
object with an `entries` list; each entry has an `id`, an
`invariant` name, a `severity`, and the probe commands with their
expected decisions. See the scaffolded file and the FP-COMM-001
example in the repo for the shape. Your rules are yours: you write
them, you maintain them, FinePrint only measures them.

## Codex needs the oracle binary (Claude Code does not)

The Codex check asks the real Codex policy checker, which lives in
a 247 MB binary that GitHub will not store (files over 100 MB are
rejected). Restore it with the repo's documented recipe — see
`tools/vendor/codex/0.149.0/VENDORED.md` — and check its SHA-256
before use. The CLI refuses to run the Codex check without the
pinned binary (it prints exactly how to restore it). Never run
oracle work on an unpinned binary.

Claude Code needs nothing: its check is pure Python, no binary, no
key, no network. That is why the five-minute path above uses it.

## Muse Code

Muse Code has no offline decision oracle — there is no local
checker to ask, and its permission system does not expose a
per-command rule format. A check therefore reports UNMEASURED
instead of a verdict:

```
UNMEASURED: muse-code has no decision source offline (see adapters/muse-code-assessment.md).
```

Exit code 3, and the bundle records the gap with its evidence
class (`no-decision-source (not measured)`). That is a deliberate
answer, not a failure: FinePrint never fabricates a verdict where
it has no decision source. Live measurement for Muse Code runs
through the `musecode-smoke` workflow in this repo — it needs your
own `MUSE_HEADLESS_KEY` secret (repo Settings → Secrets and
variables → Actions) and runs on a GitHub-hosted runner. See
`musecode-smoke/README.md`. Never paste a key into a workflow file
or a chat message.

## Troubleshooting

| You see | It means | Do this |
|---|---|---|
| `no harness config found in this directory` (exit 3) | No `fineprint.rules`, `fineprint.settings.json`, or `.claude/settings.json` here | Run `fineprint init`, then `fineprint check`. Or `cd` to the directory that has the config. |
| `no policy file found for <harness>` (exit 3) | The harness was detected but its policy file is missing | `fineprint init --harness <harness>`, then check again. |
| `oracle missing` / `restore it` (exit 3, codex) | The pinned Codex binary is not in `tools/vendor/codex/` | Follow `tools/vendor/codex/0.149.0/VENDORED.md`; check the SHA-256. |
| `UNMEASURED: muse-code has no decision source offline` (exit 3) | Muse Code cannot be measured offline | Use the `musecode-smoke` workflow for live measurement (needs your `MUSE_HEADLESS_KEY`). |
| `BLOCKED: N rule(s) broken` (exit 2) | A rule broke | Open `scorecard.html`, fix the policy, re-run. Do not edit the bundle. |
| `check failed to run` (exit 3) | The engine itself errored | Read the engine output above the line; it names the missing file or bad flag. |
| `bundle valid` fails on `verify` | The bundle was edited after sealing | Do not hand-edit bundles. Re-run the check to produce a fresh one. |
| `smoke: FAILED` | The live re-check did not answer | The Paper Test result still stands, but the live path is broken — check the harness is installed and the policy file is readable. Use `--no-smoke` to skip the smoke step. |

## What FinePrint never says

Never "safe" or "certified". A PASS means: on this date, against
these 16 rules, with this policy, no rule broke — and here is the
sealed bundle to prove it. A harness that passes today can break
tomorrow when its policy changes; re-run the check when the policy
changes. Unknown is a first-class verdict: UNRESOLVED and
UNMEASURED are reported, never silently treated as allow.
