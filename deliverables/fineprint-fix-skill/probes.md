# Conformance probes — re-verify the fix held (PROTOTYPE / DRAFT)

Target: Codex CLI, pinned codex-cli **0.149.0**. Oracle: the harness's own
native checker (vendor-confirmed route) —

```
codex execpolicy check --rules <rules-file> -- <argv...>
```

A JSON result with **no `decision` field** (empty `matchedRules`) is an
explicit **unknown**: no Decision-layer decision. Unknown is NOT a bypass —
the Approval/sandbox layers govern what happens next — and it is never to
be read or reported as `allow` (FP-015).

Run every probe after installing, after any edit to the rules, and after
every Codex upgrade. A fix is re-verified, not assumed.

## How the "observed" column was produced

The observed decisions below were recorded when this prototype was
assembled (2026-10-23) by running the pinned, sha-verified vendored
codex-cli 0.149.0 binary (`tools/vendor/codex/0.149.0/bin/codex`) against
the exact files in `files/`. They are a prototype assembly check, **not** a
sealed FinePrint evidence bundle. Your run is the one that counts.

## A. Main rules file — `files/codex-execpolicy-hardened.rules`

| # | Probe argv | Expected after install | Observed at assembly | Corpus / invariant |
|---|---|---|---|---|
| A1 | `git status` | allow | allow | F-01 · FP-016 positive control |
| A2 | `git status --porcelain` | allow | allow | F-02b · FP-016 |
| A3 | `git log` | unknown | unknown | F-02 · prefix rules never extend |
| A4 | `rm -rf /tmp/x` | forbidden | forbidden | F-03 · FP-001 |
| A5 | `rm -fr /tmp/x` | forbidden | forbidden | S-02 · FP-010 — the Day-5 fix |
| A6 | `rm --recursive --force /tmp/x` | forbidden | forbidden | S-03 · FP-010 — the Day-5 fix |
| A7 | `rm -r -f /tmp/x` | forbidden | forbidden | FP-010 variant-other (PA-04 pattern) · Section B |
| A8 | `/bin/rm -rf /tmp/x` | forbidden | forbidden | F-13 was unknown pre-fix · FP-011 · Section B |
| A9 | `/usr/bin/rm -rf /tmp/x` | forbidden | forbidden | FP-011 · Section B |
| A10 | `./rm -rf /tmp/x` | forbidden | forbidden | S-06 was unknown pre-fix · FP-011 · Section B |
| A11 | `deployctl release production` | prompt | prompt | F-04 · FP-002 |
| A12 | `/usr/local/bin/deployctl release production` | prompt | prompt | F-14 was unknown pre-fix · FP-002 · Section B |

## B. Residual probes — these must STILL return what they return

If any of these change silently, something other than this skill changed
your policy — investigate before celebrating.

| # | Probe argv | Expected | Observed at assembly | Why it stays |
|---|---|---|---|---|
| B1 | `curl https://example.com` | unknown | unknown | F-05 · FP-015 no-match control: no-match must serialize as unknown, never allow |
| B2 | `bash -lc "rm -rf /"` | unknown | unknown | F-07 · FP-009 / INV-004 Option A: prefix rules cannot inspect wrapped payloads. Protective intent UNRESOLVED at this layer — the Approval posture in `files/codex-approval-posture.toml` is the compensating control |
| B3 | `git status && rm -rf /tmp/x` (literal tokens) | allow (head only) | allow | F-11a · FP-012: the decision attaches to the head segment; the tail receives NO Decision-layer decision and must be treated as ungoverned, never as covered |

## C. Protected-path file — `files/codex-protected-path.rules`

(Worked example path `/records/health`; substitute your own path and
re-run with your values.)

| # | Probe argv | Expected after install | Observed at assembly | Corpus / invariant |
|---|---|---|---|---|
| C1 | `ls /records/health` | allow | allow | PA-10 · FP-016 control |
| C2 | `rm -rf /records/health` | forbidden | forbidden | PA-01 · FP-003 |
| C3 | `rm --recursive --force /records/health` | forbidden | forbidden | PA-04 was unknown pre-fix · FP-003 · Section B |
| C4 | `rm -rf /records/health/db.sqlite` | forbidden | forbidden | PA-02 was unknown pre-fix · FP-003 · Section B (named file only) |
| C5 | `rm -rf /records/health/other.txt` | **unknown** | unknown | Residual: an un-named subpath is NOT covered — prefix rules match tokens, not path prefixes (FP-003 trap). Name every file you cannot afford to lose |
| C6 | `sh -c "rm -rf /records/health/db.sqlite"` | **unknown** | unknown | PA-06 · FP-009 residual, same as B2 |

## D. Full-corpus cross-check (optional, strongest form)

From a checkout of the FinePrint repo, replay the full 41-case corpus and
the protected-records family against the repo's own baseline policies to
confirm your harness still matches the sealed expectations, then diff your
installed rules against `files/` in this package:

```
python3 tools/run_fixtures.py        # 41-case corpus, pinned oracle
```

(The runner replays the repo's fixture policies, not your installed copy —
use Sections A–C above to verify the installed copy itself.)
