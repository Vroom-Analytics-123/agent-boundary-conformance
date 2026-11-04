# FinePrint setup guide — install every harness, configure keys safely, record results

This guide answers three questions a fresh checkout must answer: what
commands actually work, how do I download and set up each CLI agent /
harness, and how do I configure API keys and models without leaking
anything into the repo. Every claim below states whether it was verified
on a fresh clone or is still pending; nothing is invented to fill a gap.

**Safety rules (non-negotiable, read first)**

1. Never commit a real key, token, or credential. Keys live in
   environment variables or a local `.env` file, never in a repo file.
   `.env`, `*.pem`, and `*.key` are git-ignored (see `.gitignore`).
2. Never print, log, or paste a key value — check presence by NAME only
   (`[ -n "$GEMINI_API_KEY" ]` and report yes/no, never the value).
3. Agent processes in live runs hold only the dummy string
   `dummy-local-only`. Provider auth goes through a localhost proxy
   whose operator supplies the real credential through their own
   mechanism (the live-agents `proxy.py` surrogate pattern). No raw key
   appears in any record, log, or published file.
4. CI uses GitHub repo secrets only (`${{ secrets.NAME }}`), passed to
   exactly one step, never echoed, never dumped with `set -x`.
5. Results are labelled: **UNSEALED** until a signed bundle verifies.
   Unsealed runs move no badge and change no scorecard score.

## Prerequisites

- Python 3.12, `pytest` (`python3 -m pip install pytest` — the suite
  itself is stdlib-only), `git`, `node` + `npm` (CLI installs and the
  Codex restore recipe).
- ~350 MB transient disk for the Codex restore (tarball + 258 MB binary).

## Part A — commands that work with no key (fresh-clone verified)

All of these were run on a fresh clone of main for this guide.

```bash
git clone https://github.com/Vroom-Analytics-123/agent-boundary-conformance.git
cd agent-boundary-conformance
python3 -m pytest tests/ -q
```

- **Without the pinned Codex binary:** 103 passed, 3 failed — all three
  failures are the oracle tests failing CLOSED on the pin mismatch
  (that is the gate working, not a defect).
- **With the binary restored (recipe below):** 106 passed
  (90 subtests), matching the submission's Reproduce block.

```bash
# Restore the pinned oracle FIRST: the binary is git-ignored (GitHub
# rejects blobs over 100 MB). Recipe + pinned sha256 live in
# tools/vendor/codex/0.149.0/VENDORED.md; verified end to end:
cd /tmp && mkdir codex-restore && cd codex-restore
npm pack "@openai/codex@0.149.0-linux-x64"
mkdir lin && tar -xzf openai-codex-0.149.0-linux-x64.tgz -C lin
sha256sum lin/package/vendor/x86_64-unknown-linux-musl/bin/codex
# must print bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827
cp lin/package/vendor/x86_64-unknown-linux-musl/bin/codex \
   <repo>/tools/vendor/codex/0.149.0/bin/codex
cd <repo>
python3 tools/run_fixtures.py      # verdict table, ~10s
```

`run_fixtures.py` prints `pass=40 fail=1` with decisions
allow 6 / forbidden 11 / prompt 4 / unknown 20 (the post-fix table).
The single fail is the documented S-02 bookkeeping artifact. Note: the
script exits 1 whenever any case fails, so it exits 1 on this expected
result — a human reading the table sees PASS; a script must not treat
exit 1 alone as breakage (see Known gaps).

```bash
python3 framework/scorecard/build_scorecard.py        # v2 SVG, regenerates byte-identical
python3 framework/scorecard/build_scorecard_v3.py      # v3 SVG, regenerates byte-identical
python3 mcp/server.py                                 # stdio MCP server, no key, nothing executes
python3 -m pytest tests/test_mcp_server.py -q         # MCP end to end (needs the oracle for run_check)
```

Paper adapters run offline with no key, but note the working directory:
`adapters/<key>/test_engine.py` uses relative policy paths, so run it
from inside its own directory:

```bash
cd adapters/cursor && python3 test_engine.py   # OK (fails from repo root: policy file not found)
cd ../gemini-cli && python3 test_engine.py     # 33 passed
cd ../opencode && python3 test_engine.py       # ALL TESTS PASSED
```

Replication (see `REPLICATION.md` for the full contract):

```bash
./tools/replicate.sh                                # default: Day-2 bundle
./tools/replicate.sh evidence/postfix-2026-10-22/bundle.json
```

- Default Day-2 target on current main: `DIFF` (exit 1) — inputs have
  legitimately drifted since the Day-2 seal, and the script names the
  drifted files. This is the documented behaviour on a post-seal tree,
  not a breakage. Pin-intact commits are listed in `REPLICATION.md`.
- Postfix target: currently `ERROR` (exit 2) — see Known gaps. The
  inputs match the pins and the oracle verifies; the failure is the
  `run_fixtures.py` exit-1-on-artifact rule (below), not the evidence.

## Part B — per-harness setup, keys, and models

Status key: **verified** = install + run path confirmed on main or by a
fresh-clone test; **pending** = the repo does not yet contain that piece
(a fresh user cannot complete it from the repo alone).

| Harness | Install (pin) | Key env var / CI repo secret | Model | Run (records) |
|---|---|---|---|---|
| Codex (oracle) | verified: npm recipe above, 0.149.0, sha256 pinned | none (offline oracle) | none | `python3 tools/run_fixtures.py` → `evidence/reruns/` |
| Amp (oracle) | vendor script present at `tools/vendor/amp/0.0.1792680614-g8973a3/` (version pinned by path); install not re-run in this audit | none (offline oracle) | none | `python3 tools/run_amp_corpus.py` |
| Copilot CLI | verified: `npm install -g @github/copilot@1.0.105` (workflow-pinned) | `COPILOT_GITHUB_TOKEN` / repo secret of the same name; pass `--secret-env-vars=COPILOT_GITHUB_TOKEN` | unpinned (record the version the run reports) | `python3 copilot-cli/smoke_runner.py`; series: `framework/scorecard/copilot-live-v1/runners/series_runner.py` |
| Gemini CLI (native) | verified: `npm install -g @google/gemini-cli@0.66.0` (workflow-pinned) | `GEMINI_API_KEY` / repo secret of the same name | provider default for the native route; record `gemini --version` | `python3 gemini-cli/smoke_runner.py` |
| Gemini CLI (cheaper route) | pending: translating proxy is local-only, not in the repo | proxy operator's credential via surrogate; agent holds `dummy-local-only` | `gemini-2.5-flash` (fixed for the series) | series runner in `framework/scorecard/gemini-live-v1/runners/` once the proxy is published |
| Claude Code (paper) | verified: `adapters/claude-code/` runs offline (see Part A) | none for the paper route | n/a (config evaluation) | `adapters/claude-code/run_corpus.py`, `test_engine.py` |
| Claude Code (live, cheaper route) | pending: proxy + smoke are local-only, not in the repo | proxy operator's credential via surrogate; agent holds `dummy-local-only` | `claude-sonnet-4.5` (fixed for the series) | pending until the smoke package publishes |
| Cursor | pending on main: `cursor/smoke_runner.py` is branch-only; workflow install is unpinned (no version pin) | `CURSOR_API_KEY` / repo secret of the same name; requires a user API key (paid plan) | record the version the run reports | pending until the runner lands on main |
| Muse Code | pending on main: `musecode-smoke/install.sh` + `smoke_runner.py` are branch-only | `MUSE_HEADLESS_KEY` / repo secret of the same name | pinned per workflow; record the version | pending until the runner lands on main |
| OpenCode | 1.19.5; local install via the official route (verify `opencode --version` reads 1.19.5 after install — the installer itself is unpinned, so the version check is the pin) | proxy operator's credential via surrogate; agent holds `LOCALPROXY_API_KEY=dummy-local-only` | beam arm via localhost proxy on port 8893 | `framework/scorecard/opencode-live-v1/runners/matrix.py`, then `tally.py` |
| Goose | pending (install step): package requires the Goose 1.57.0 binary but gives no install command | proxy operator's credential via surrogate; agent holds `dummy-local-only` | beam-free via live-agents proxy on port 8894 | `framework/scorecard/goose-live-v1/runners/matrix.py`, then `tally.py` |
| Omnigent | pending (install + re-run docs): 0.19.1, runners + `agent_template.yaml` published, but the package README gives no install or re-run commands | proxy operator's credential via surrogate; agent holds `dummy-local-only` | beam-free + `muse-spark-1.1` arms | `framework/scorecard/omnigent-live-v1/runners/matrix.py` once install docs exist |
| Live reference agents (Strands 1.62.0, LangGraph 1.2.16, CrewAI 1.15.28, Hermes, OpenClaw 2026.10.6) | pending (per-agent installs): drivers + proxy published, versions stated, install commands not documented | proxy operator's credential via surrogate; agent holds `dummy-local-only` | beam arm + `muse-spark-1.1` arm | `framework/scorecard/live-agents-v1/runners/`; copy `framework/scorecard/scenarios-v1.json` to `/tmp/scenarios-v1.json` first (per that package's README) |
| Pi | pending: no in-repo runner (survey row: no permission system by design); the fix lives on a fork branch, not in this repo | none | none | none in-repo |
| Nemotron (model proposes, checker decides) | no install (API only) | `NEBIUS_API_KEY` (env only, never printed/logged/written to evidence) | `nvidia/nemotron-3-super-120b-a12b` | `NEBIUS_API_KEY=... python3 tools/run_nemotron_demo.py --invariants FP-001,FP-002,FP-003 --model nvidia/nemotron-3-super-120b-a12b --policy fixtures/policies/default.rules --out evidence/my-nebius-run/ --direct` (needs key; never point `--out` at a sealed directory) |

## Part C — configuring keys and models

1. Copy `.env.example` to `.env` and fill in only the keys you have.
   `.env` is git-ignored; never commit it, never paste it anywhere.
2. Prefer one key per harness run, set in the environment of that run
   only. In CI, create the matching repo secret (Settings → Secrets →
   Actions) and let the workflow pass it to exactly one step.
3. For localhost-proxy runs (OpenCode, Goose, Omnigent, live agents,
   Gemini/Claude cheaper routes): the agent process gets only the dummy
   string. The proxy operator — you, on your own machine — supplies
   provider auth through your own mechanism. Never put the real key in
   a runner file, a record, or a log.
4. Record the model + version in every record (model fixed within a
   series; a model change is a NEW disclosed series, never mixed).
5. Record results under the harness's package directory
   (`framework/scorecard/<harness>-live-v1/` with SUMMARY.md +
   tallies.json + runners/) and label them UNSEALED unless a signed
   bundle verifies. Raw record trees with scratch fixtures stay local
   and are never committed (they trip secret scanners and leak
   nothing, but they are not publication artefacts).

## Known gaps (honest list — these are the work, not footnotes)

1. **Branch-only runners.** Cursor, Muse Code, and the OpenCode series
   workflow reference paths (`cursor/`, `musecode-smoke/`,
   `opencode/`) that do not exist on main. Dispatching those workflows
   from main fails before any measurement. They work only when
   dispatched from their branches. Landing the runners on main (or
   repointing the workflows) is the single biggest reproducibility fix.
2. **Missing install commands.** Goose (binary prerequisite, no install
   command), Omnigent (no install/re-run docs), and the live-agents
   per-agent installs are not documented in their packages.
3. **Unpinned installs.** The Cursor workflow install and the OpenCode
   local install route carry no version pin; the version check after
   install is the only pin. Pin them or record the installed version
   in every record.
4. **Postfix replication ERROR.** `tools/replicate.sh
   evidence/postfix-2026-10-22/bundle.json` fails at the rerun step
   because `run_fixtures.py` exits 1 on the documented S-02 artifact
   fail and the script treats any nonzero exit as ERROR. Fix options:
   (a) teach `replicate.sh` to accept exit 1 when the rerun JSON shows
   only the expected artifact fail; or (b) teach `run_fixtures.py` to
   exit 0 when failures match the documented artifact. Until then, the
   postfix path cannot print PASS on current main.
5. **`run_fixtures.py` exit code.** Same root cause as (4): exit 1 on
   the expected 40/1 result. Humans read the table; scripts must check
   the table, not just the exit code.
6. **Paper-adapter working directory.** `adapters/<key>/test_engine.py`
   must run from inside its own directory (relative policy paths).
7. **`.gitignore` gap (fixed on this branch).** `.env`, `*.pem`, and
   `*.key` were not ignored. They are now; verify with
   `git status --short` after creating a `.env` — it must not appear.
8. **Cheaper-route proxies are local-only.** The Gemini translator and
   the Claude pass-through proxy (and their auth wiring) are not in
   the repo. Their runners reference them; publishing the proxy
   pattern without the auth wiring is the remaining step.
