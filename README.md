# Agent Boundary Conformance — FinePrint

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache-2.0-blue.svg)](LICENSE) [![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/) [![MCP server](https://img.shields.io/badge/MCP-stdio-green.svg)](mcp/README.md) [![CI](https://github.com/Vroom-Analytics-123/agent-boundary-conformance/actions/workflows/ci.yml/badge.svg)](https://github.com/Vroom-Analytics-123/agent-boundary-conformance/actions/workflows/ci.yml)

## What this is

FinePrint measures whether an AI coding agent's *enforced* limits match its *stated* limits. You write security rules for your agent ("never silently delete", "deploys ask first"); FinePrint asks the agent's **own rule checker** what it actually decides, compares that with what a human is asked and what actually happens, and reports **pass / fail / unknown** with sealed, replayable evidence.

It is a building inspector, not a firewall: it never certifies anything "secure", never blocks anything itself, and it re-runs on every agent release, because a new version can move a decision the last one got right.

**Status: the method is proven, the verdict is deliberately NARROW** — two vendor-confirmed decision routes (Codex + Amp), limitations stated on their face ([docs/LIMITATIONS.md](docs/LIMITATIONS.md)). The living status page is [docs/PROJECT_PATHWAY.md](docs/PROJECT_PATHWAY.md).

![FinePrint Check demo — install, check, verdict + bundle](assets/fineprint-check-demo.gif)

## Use it

### 1. Check your agent's rules — one command, zero config, no account, no key

Clone FinePrint once, anywhere — the clone is just the engine. Then run the check from **your own project directory**, where your rules live; the verdict and evidence bundle are written there:

```bash
git clone https://github.com/Vroom-Analytics-123/agent-boundary-conformance.git   # once, anywhere
cd ~/my-project                                                                   # where YOUR rules live
python3 /path/to/agent-boundary-conformance/fineprint init    # starter rules, skip if you have them
python3 /path/to/agent-boundary-conformance/fineprint check   # verdict + sealed bundle in ./fineprint-evidence/
```

It auto-detects your agent's rules file in the current directory: `fineprint.rules` (Codex), `fineprint.settings.json` or `.claude/settings.json` (Claude Code). Claude Code checks with no download at all; a Codex check needs the pinned oracle restored into the clone first — recipe: [tools/vendor/codex/0.149.0/VENDORED.md](tools/vendor/codex/0.149.0/VENDORED.md).

`PASS` (exit 0) or `BLOCKED` (exit 2 — a rule broke; open `scorecard.html` in the evidence directory, fix the rules, re-run). `UNRESOLVED` means your rules do not answer that probe — reported, not hidden. Full guide: [INTEGRATION.md](INTEGRATION.md).

### 2. 13 UNRESOLVED? That is the honest result — and the wall is the answer

Your rules cannot see inside wrapped shells or unnamed paths, so some probes come
back `UNRESOLVED` — reported, never treated as allow. Two honest moves: write
rules for the situations you care about, and let the wall carry what rules
alone never can. The walk-through: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

### 3. Stop the harm while the agent works — the wall, then the log

The check measures; the wall enforces. The default is a protective denylist: credential reads, destructive deletes, exfiltration of protected files, and unapproved deploys are blocked; normal work anywhere is allowed. Folder confinement is opt-in (`--confine`).

```bash
./fineprint gate run -- cat notes.txt        # allows, exit 0
./fineprint gate run -- rm -rf notes.txt     # blocked, exit 2 (rule DENY-DELETE)
./fineprint gate run -- python3 read_key.py  # the wall hides ~/.ssh — the read fails, nothing leaks
./fineprint gate log --log audit.jsonl       # tried X → blocked by rule Y → will always be blocked
```

A wall denial looks like a plain `FileNotFoundError` — the wall hides, it does
not scold; `gate log` is where the story is. Mechanism, signed definition packs,
and the limits stated plainly: [docs/FREE_GATE.md](docs/FREE_GATE.md). No
terminal? The [desktop app](apps/desktop/README.md) is the wall's live feed.

### 4. Keep it green

`fineprint doctor` reports in one command what can run on this machine — your
rules file, the pinned oracle, the wall's preconditions — with the remedy for
each gap. Add
[one CI file](docs/FREE_CHECK_ACTION.md) and the check runs on every pull
request — red means a rule broke, the evidence bundle is downloadable from the
run. And re-run the check after every agent release: a new version can move a
decision the last one got right.

### 5. From your agent — the MCP server

`python3 mcp/server.py` (stdio) gives Claude Code, Codex, and any MCP client four tools — `check_command`, `list_invariants`, `measurement_routes`, `run_check`. See [mcp/README.md](mcp/README.md) and the [skill](mcp/SKILL.md).

### 6. Reproduce the measurements (researchers)

```bash
# Restore the pinned oracle first: the 258 MB codex-cli 0.149.0 binary is
# git-ignored (GitHub rejects blobs > 100 MB). Recipe + pinned sha256:
# tools/vendor/codex/0.149.0/VENDORED.md — in short:
cd /tmp && mkdir codex-restore && cd codex-restore
npm pack "@openai/codex@0.149.0-linux-x64"
mkdir lin && tar -xzf openai-codex-0.149.0-linux-x64.tgz -C lin
mkdir -p <repo>/tools/vendor/codex/0.149.0/bin   # bin/ is git-ignored; it does not exist in a fresh clone
cp lin/package/vendor/x86_64-unknown-linux-musl/bin/codex <repo>/tools/vendor/codex/0.149.0/bin/codex
# sha256 must print bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827
cd <repo>
python3 -m pytest tests/ -q        # full suite
python3 tools/run_fixtures.py      # the verdict table, ~10s
```

Without the binary, the 3 oracle tests fail closed with a pinned-oracle mismatch — that is the gate working, not a code defect.

## What it found

41 probe commands replayed against Codex's own rule checker (pinned codex-cli 0.149.0). The question is how often the rulebook answers at all:

| | allow | prompt | forbidden | unknown |
|---|---|---|---|---|
| Before the fix | 6 | 4 | 9 | 22 |
| After the fix | 6 | 4 | 11 | 20 |

The fix moved two spelling variants (`rm -fr`, `rm --recursive --force`) from unknown to forbidden, sealed as `evidence/postfix-2026-10-22/bundle.json` (Merkle root `5a974fe6…`). **"Unknown" is NOT a bypass** — it means the written rules don't decide it; the agent's approval prompts and sandbox still govern what happens. And the corpus is deliberately weighted toward tricky variants: 54% unknown is a property of this probe set, never a real-world rate.

## The harness scorecard

![FinePrint harness scorecard — combined live-basis view (PROVISIONAL)](framework/visuals/scorecard.svg)

Sixteen harnesses scored on the same 24 scenarios across three layers — **Decision / 25, Approval / 25, Effect / 50** — weighted by impact. Higher = stronger hold rate, **not a security grade**; rows mix measurement routes, so compare rows only within the same route. No harness wins cleanly: live leader **Amp 72.03** still lets credential reads execute 8/8, and Codex forbids every deletion command on argv yet 7 of 12 deletions execute via `unlink`. The row-by-row findings: [framework/scorecard/v4-scorecard.md](framework/scorecard/v4-scorecard.md).

Full table + method ([framework/SCORING-v4.md](framework/SCORING-v4.md)) + sealed evidence ([evidence/live-2026-11-04/](evidence/live-2026-11-04/)) — the combined view is PROVISIONAL until its promotion gets the owner's word.

## How it works

1. **The problem** — an agent must never do X: delete, exfiltrate, deploy, whatever you forbade. But does it actually stop?
2. **The rule** — you write the rule as an invariant, a statement of intent in plain words ("never silently delete").
3. **The probe** — FinePrint replays probe commands against the agent's own checker. Never a re-implementation.
4. **The three layers, compared not chained** — Decision (what the rules decide), Approval (does a human gate intervene), Effect (what actually happened — ground truth). A disagreement between any two is a finding; silence is reported as unknown, never as allow.
5. **Finding → fix → re-measure** — every finding ships with a drafted fix, and the fix only closes when the suite re-runs and re-verifies it.

The method was proven in depth on two agents (Codex, Claude Code) before spreading across sixteen; adding a target follows [docs/EXTENDING.md](docs/EXTENDING.md).

## Docs

| Document | What it is |
|---|---|
| [docs/EXPLAINER.md](docs/EXPLAINER.md) | **Start here if the idea is new to you** — the full plain-language foundation |
| [docs/PROJECT_PATHWAY.md](docs/PROJECT_PATHWAY.md) | The living status page — objectives, invariants, what's waiting on the founder |
| [docs/BACKGROUND.md](docs/BACKGROUND.md) | Why it matters: verified incidents, attack surface, the catalogue, fixes filed upstream, Nemotron + Meta/Muse attribution |
| [docs/DEMOS.md](docs/DEMOS.md) | All the demo GIFs and how each was recorded |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | **What the evidence does NOT support — read before citing any result** |
| [docs/FRAMEWORK.md](docs/FRAMEWORK.md) | The harness-neutral framework: invariant schema, adapter contract, the three layers |
| [docs/EXTENDING.md](docs/EXTENDING.md) | How to add a harness or framework target |
| [docs/catalogue/](docs/catalogue/) | The invariant catalogue: 16 parameterized invariants with per-target translations |
| [INTEGRATION.md](INTEGRATION.md) | The Check CLI, written for a junior dev |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | **The user journey, step by step** — check → UNRESOLVEDs → wall → log → keep it green, with real captured output |
| [docs/DOCUMENT_MAP.md](docs/DOCUMENT_MAP.md) | Every doc, its status, and what it holds |

## License

Apache-2.0 — see [LICENSE](LICENSE). Copyright 2026 Anish Kumar.
