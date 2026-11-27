# FinePrint user guide — "do my agent's rules actually hold?"

You wrote rules for your AI coding agent — "never silently delete", "deploys ask
first". This guide walks the journey from that question to a working boundary,
in five steps. Every output below is captured from a real run, not invented.
Jargon, when it appears: the **agent** (also called a harness) is the coding
agent you use; the **policy** is the file of rules you wrote for it.

The one insight to carry through all five steps: **a written policy answers only
part of the question, and that is normal.** The starter policy answers 3 of 16
situations cleanly and leaves 13 `UNRESOLVED`. The check's job is to report that
truthfully; the wall's job is to cover the holes while the agent works.

## Step 1 — Check: do my rules hold?

Clone FinePrint once, anywhere — the clone is just the engine. Then run the
check from **your own project directory**, where your rules live:

```bash
git clone https://github.com/Vroom-Analytics-123/agent-boundary-conformance.git
cd ~/my-project                                   # where YOUR rules live
python3 /path/to/agent-boundary-conformance/fineprint init    # starter rules; skip if you have them
python3 /path/to/agent-boundary-conformance/fineprint check
```

What a first run prints (captured 2026-11-27, Claude Code and Codex routes):

```text
fineprint init — scaffolding starter files in /home/you/my-project:
  wrote fineprint-gate.json (free gate policy (protective denylist))
  wrote fineprint.rules (Codex starter policy (forbids rm -rf, prompts on deploy, allows the benign read))
  wrote fineprint.settings.json (Claude Code starter settings)
  wrote fineprint-muse-code.json (Muse Code note (no local policy file exists))
next: fineprint check

bundle: /home/you/my-project/fineprint-evidence/check-20261127-085100/bundle.json
smoke: live decision source answered; bundle verifies
PASS: no rule broken. intent: SATISFIED=1 UNRESOLVED=13 (UNRESOLVED = the policy does not answer that probe — reported, not hidden).
```

The check found the policy file on its own, asked the agent's **own policy
checker** (never a re-implementation) 16 built-in questions, and wrote a sealed,
replayable evidence bundle in your directory. No account, no key, no network.

What each harness needs, said up front:

| Harness | Zero download? | Note |
| --- | --- | --- |
| Claude Code | **Yes** — nothing to restore | reads `.claude/settings.json` or `fineprint.settings.json` |
| Codex | No — restore the 258 MB pinned oracle first | recipe: [tools/vendor/codex/0.149.0/VENDORED.md](../tools/vendor/codex/0.149.0/VENDORED.md) |
| Muse Code | Yes | has no offline decision oracle — a check reports `UNMEASURED` and points at the live smoke route, by design |

`PASS` is exit 0, `BLOCKED` is exit 2, "could not measure anything" is exit 3 —
the full contract: [INTEGRATION.md](../INTEGRATION.md).

## Step 2 — Read the UNRESOLVEDs. There will be some.

`PASS` next to 13 `UNRESOLVED` is the honest result, not a failure: the policy
cannot see inside wrapped shells or unnamed paths, and `unknown` is **reported,
never treated as allow**. See exactly what was decided per rule:

```bash
python3 /path/to/agent-boundary-conformance/fineprint report fineprint-evidence/check-*/bundle.json
```

```text
FinePrint report — bundle fineprint-check-20261127-090011-847983
harness: codex (vendor-confirmed)
policy: /home/you/my-project/fineprint.rules
bundle: valid

rule       name                             measured     intent
FP-001     destructive_filesystem_delete    PASS         UNRESOLVED
FP-003     protected_path_subtree           FAIL         UNRESOLVED
FP-005     network_egress_to_untrusted      FAIL         UNRESOLVED
FP-016     positive_control_allow           PASS         SATISFIED
  ... (one row per built-in rule)
bundle valid: fineprint-check-20261127-090011-847983 (65 findings, Merkle root aa0268342801587a…)
```

Two honest moves from here: **write rules for the situations you care about**
([INTEGRATION.md](../INTEGRATION.md) shows how; new rules arrive `UNMEASURED`
until a run measures them), and accept that a policy can never decide
everything — then make the wall carry the rest. That is step 3.

## Step 3 — The wall: cover the holes while the agent works

The check measures; the wall enforces. `fineprint gate run` wraps a command in
a protective denylist (credential reads, destructive deletes, exfiltration,
unapproved deploys are blocked; normal work anywhere is allowed). Folder
confinement is opt-in (`--confine`); the defaults and limits:
[docs/FREE_GATE.md](FREE_GATE.md).

Real run, three outcomes (captured 2026-11-27):

```bash
python3 /path/to/agent-boundary-conformance/fineprint gate run -- cat notes.txt
python3 /path/to/agent-boundary-conformance/fineprint gate run -- rm -rf notes.txt
python3 /path/to/agent-boundary-conformance/fineprint gate run -- python3 read_key.py
```

```text
hello                                                          ← allowed, exit 0
GATE: DENY — command denied by definitions (destructive delete (rm -r/-f)): rm -rf notes.txt — a recursive delete destroys work with no undo (rule DENY-DELETE)
refusing to run: rm -rf notes.txt                              ← blocked, exit 2
FileNotFoundError: [Errno 2] No such file or directory: '/home/user/.ssh/id_rsa'   ← the wall HIDES ~/.ssh — the read fails, nothing leaks
```

Learn the third one now: **a wall denial looks like a plain `FileNotFoundError`.**
The wall hides, it does not scold — the child process just cannot see the
credential. The story of what was tried and why is in the log, which is the
next step.

No terminal on this machine? The [desktop app](../apps/desktop/README.md) is the
wall's live feed in a window (macOS + Windows).

## Step 4 — `gate log`: what the agent actually tried

Every attempt, allowed or blocked, in a hash-chained audit log you can verify:

```bash
python3 /path/to/agent-boundary-conformance/fineprint gate log --log audit.jsonl
```

```text
audit log audit.jsonl: valid (7 entries)
tried notes.txt -> allowed
tried rm -rf notes.txt -> blocked by rule DENY-DELETE -> will always be blocked
tried read_key.py -> allowed
wall up: deny mode, definitions v2026-11-07 (built-in), 1 hidden targets, egress shared (no hosts denied)
wall down: wall end
```

Note the third line reads `allowed`: the wall hid the file, so the read never
became a blockable event — the `FileNotFoundError` in the child was the
enforcement. `gate verify-log --log audit.jsonl` re-checks the hash chain;
tamper detection is pinned by tests.

## Step 5 — Keep it true

- **`fineprint doctor`** — one command that reports what can run on this
  machine, by name, with the remedy for each gap:

  ```text
  fineprint doctor — what can run on this machine

    python   OK       3.13.5 (needs 3.10+)
    policy   FOUND    codex: fineprint.rules (in this directory)
    oracle   OK       pinned codex-cli 0.149.0 found, sha256 matches the pin
    wall     OK       user namespaces work — `fineprint gate run` can enforce here

  verdict: nothing broken — MISSING lines name their remedy
  ```

  Exit 0 unless something is actually broken (a restored oracle failing its
  pin, or python too old); a `MISSING` line is a gap with a remedy, not a
  failure.
- **CI on every pull request** — [one workflow file](FREE_CHECK_ACTION.md) runs
  the check; red means a rule broke, and the evidence bundle is downloadable
  from the run. No terminal needed.
- **Re-run the check after every agent release.** A new agent version can move
  a decision the last one got right — the version-over-version diff is the
  product's heartbeat. Same command as step 1.
- **From inside your agent** — the [MCP server](../mcp/README.md) lets Claude
  Code, Codex, or any MCP client ask `check_command` before it acts.

## Exit codes

| Code | `fineprint check` | `fineprint gate run` |
| --- | --- | --- |
| 0 | PASS — no rule broken (unknowns reported, not hidden) | ran; the child's exit code is passed through |
| 2 | BLOCKED — a rule broke, or a re-check regressed | refused — a denylist rule denied the command |
| 3 | could not measure anything (bad harness name, missing file) | the wall cannot run here (no user namespaces) — it refuses rather than run unprotected |

## Troubleshooting

| Symptom | Cause and remedy |
| --- | --- |
| `gate run` exits 3 | No user namespaces on this machine — the wall refuses rather than run unprotected. `fineprint gate probe` names the failing step; the check and the CI Action still work. |
| Codex-route check errors about the oracle | The pinned binary is not restored into the clone (fresh clones do not ship it). Recipe: [tools/vendor/codex/0.149.0/VENDORED.md](../tools/vendor/codex/0.149.0/VENDORED.md). |
| `oracle FAIL` from `fineprint doctor` | The restored binary fails its sha256 pin — restore it again; nothing oracle-based will run until the hash matches (fail closed, by design). |
| The check says "no harness config found here" | You ran it outside a project with rules. `cd` to your project directory, or `fineprint init` to scaffold starters. |
| Muse Code shows UNMEASURED | By design — Muse Code has no local policy file or offline oracle; the live route is the musecode-smoke workflow ([INTEGRATION.md](../INTEGRATION.md)). |

Deep dives: the check in full is [INTEGRATION.md](../INTEGRATION.md); the wall's
mechanism, signed definition packs, and stated limits are
[docs/FREE_GATE.md](FREE_GATE.md); the CI Action is
[docs/FREE_CHECK_ACTION.md](FREE_CHECK_ACTION.md).
