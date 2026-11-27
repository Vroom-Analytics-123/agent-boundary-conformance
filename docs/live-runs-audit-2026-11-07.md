# Live-runs audit — can the repo itself run all 14 harnesses live?

Date: 2026-11-07. Branch-only (`feature/attribution-block-vs-not-attempted`).
Not merged to main; main stays frozen for judging until the Nov 9 ceremony.

## Method

Every verdict below was established from the repo itself: workflow files,
runner scripts, adapter manifests, bundle `bundle.json` provenance fields,
and bundle SUMMARY files. Nothing here rests on memory or on a summary.
Where the repo does not settle a point, it is marked UNKNOWN with what
would settle it. A vendor oracle, a paper adapter, and a localhost stub
are never called a live run.

The 14 harnesses are the 14 live-basis rows of
`framework/scorecard/v4-scorecard.md` (scoring v4, provisional). The
decision-only rows (Claude Code paper, Cursor, Pi) are covered separately
below because the question "can the repo do live runs on all harnesses"
is sharpest exactly where there is no live run.

## Per-harness verdicts

| Harness | Live-run path (exact) | Auth needed — met? | Live evidence cited | Gap |
|---|---|---|---|---|
| Amp | `framework/scorecard/amp-live-v1/run_one.py` + `matrix.py`: `amp -x "Execute the following shell command: <cmd>" --mode medium --executor local --stream-json --settings-file policy-settings.json`; binary `~/workspace/amp-spike/package/amp` | Owner ChatGPT-subscription login (vroomanalytics123@gmail.com, authorized Nov 4, 06:56 PT). Met at run time, on this machine. | `evidence/live-2026-11-04/amp-live/`, sealed, 48 cells, Merkle `1b2bea1c…` | Binary + login live outside the repo. Model unobservable (server-side choice inside mode `medium`) — a re-run may not use the same model. No sandbox (executor local, container as root). Approval observed only as headless ask-rejection, never a TUI dialog. |
| OpenClaw | `framework/scorecard/live-agents-v1/runners/openclaw_run_one.py` (+ `proxy.py` in the same dir); binary `~/openclaw-stage4-install/node_modules/openclaw/openclaw.mjs` | Dummy apiKey in gateway config; real provider call via localhost proxy + dynamic-credential surrogate. Met. | `evidence/live-2026-11-04/live-agents/`, sealed, 480 runs (5 agents × 2 arms × 2 repeats), Merkle `b1f4c971…`; also Oct 23 campaign bundle `evidence/live-campaign-2026-10-23/openclaw/` (47 files). | Gateway binary outside the repo. Sandbox mode off (Docker absent) — confinement UNMEASURED. Only its own exec boundary measured (standing caveat). |
| Claude Code (live) | `framework/scorecard/claudecode-live-v1/run_series.py`: CLI 2.1.318, stream-json, localhost proxy port 8898, model `claude-sonnet-4.5` fixed | Dummy `ANTHROPIC_API_KEY` in the CLI env; real credential attached by the proxy via surrogate. Met at run time. | `evidence/live-2026-11-04/claudecode-live/`, sealed, 48 cells, Merkle `7993b30e…` | **The proxy script is NOT in the repo.** `run_series.py` expects a pass-through proxy on port 8898 and the package README references `proxy.py`, but the file is absent from the bundle and the package; it exists only locally at `~/workspace/claudecode-{cheaper,fresh}/proxy.py`. A fresh checkout cannot re-run Claude live. Separately, repo secret `ANTHROPIC_API_KEY` exists (created Nov 4) but no workflow references it and its purpose is undocumented — UNKNOWN whether it backs the proxy. |
| Muse Code | (a) Actions dispatch `.github/workflows/musecode-matrix.yml` + `musecode-smoke.yml`, secret `MUSE_HEADLESS_KEY`, runner `pilot_runner.py` on branch `musecode-smoke` (the main copy only registers the workflow); (b) local `framework/scorecard/musecode-v1/v1_runner.py` + `approver.py`, `muse serve`, local Muse Code 1.4.14 | `MUSE_HEADLESS_KEY` (repo secret, created Nov 2). Met. | `evidence/live-2026-11-04/musecode-v1/`, sealed, 48 cells, Merkle `23e92ebc…`; `musecode-n3-rerun/`, 39 runs, Actions run 41753257547. | The Actions runner lives on the `musecode-smoke` branch, not main. The local binary's location is not recorded in the repo (the runner invokes `muse serve`; no `muse` binary is on this shell's PATH). Read tool is the harm channel; zero shell executions anywhere. Sandbox (bwrap) failed to start in cells. |
| Hermes Agent | `framework/scorecard/live-agents-v1/runners/hermes_run_one.py` (PTY, manual mode); binary `~/workspace/hermes-scratch-home/.local/bin/hermes` | Dummy `HERMES_GATEWAY_KEY`; real provider call via local proxy + surrogate. Met. | `live-agents/` sealed bundle (part of the 480). Also Oct 23 campaign bundle `evidence/live-campaign-2026-10-23/hermes/` (75 files). | Binary outside the repo. Docker absent, so the container backend is unmeasured. Smart/guardian (stochastic) mode unmeasured. No workflow. |
| Omnigent | `framework/scorecard/omnigent-live-v1/runners/run_one.py` + `matrix.py` (per-run local server + agent YAML; proxy port 8893; arms cheaper `beam-free` / meta `muse-spark-1.1`) | Dummy key; proxy + surrogate. Met. | `evidence/live-2026-11-04/omnigent-live/`, sealed, 96 cells, Merkle `3d7c4c3c…`; Oct 23 campaign bundle. | The proxy script is not shipped in the package (the runner expects a proxy on port 8893). Local Omnigent 0.19.1 venv + server outside the repo. No workflow. |
| Gemini CLI | (a) Actions `.github/workflows/harness-gemini.yml`, secret `GEMINI_API_KEY` (exists, created Nov 4), runner `gemini-cli/smoke_runner.py`; (b) local translator route `framework/scorecard/gemini-live-v1-full/runners/series_runner_full.py` + `translator/proxy.py` (local only, `~/workspace/gemini-cli-cheaper/translator/`), model `gemini-2.5-flash` fixed | (a) `GEMINI_API_KEY` secret — exists. (b) Dummy key + surrogate via the local translator proxy. Met. | `evidence/live-2026-11-04/gemini-live-full/`, sealed, 48 cells, Merkle `d841b76e…`; `gemini-live/`, 14 cells, sealed. Both from route (b). | **The workflow path does not reproduce the sealed evidence.** The native CLI attempt (Actions run 41782356318) failed: `FAIL_NO_DECISION`, exit 173, sandbox failed to start (auth fine). The evidence came from the local translator route, whose translator + proxy live outside the repo. Policy covers rm spellings only — exfiltration / deploy / credential cells have no applicable deny rule. |
| Codex | `framework/scorecard/codex-live-v1/run_one.py` + `run_matrix.sh`: `codex exec --skip-git-repo-check --ephemeral -m gpt-5.6-sol -s workspace-write --json`; binary `~/workspace/codex-live-v1-retry/restore/lin/package/vendor/…/bin/codex` (verified present) | Codex CLI login (ChatGPT account) on the local machine. **UNKNOWN whether met now** — the repo records no login, account, or OAuth note anywhere in the codex package; the Nov 4 run happened, so some login existed then. | `evidence/live-2026-11-04/codex-live-v1/`, sealed, 48 cells, Merkle `00a71b7e…` | Auth undocumented. Binary outside the repo. Per-cell model was requested (`gpt-5.6-sol`) but not witnessed in the `--json` stream. No workflow. |
| Copilot CLI | Actions dispatch `.github/workflows/harness-copilot.yml`, secret `COPILOT_GITHUB_TOKEN` (exists, created Nov 4); runners `copilot-cli/smoke_runner.py`, `series_runner.py`, `framework/scorecard/copilot-full-v1/runners/full_runner.py` — all on main | Fine-grained PAT with Copilot Requests permission, passed via env on the runner step only. Met. | `evidence/live-2026-11-04/copilot-full/`, sealed, 48 cells, Actions run 41859562920, Merkle `6685d7a9…`; `copilot-live/`, 15 cells, run 41768181178. | Model unpinned and not recorded (`null` by design) — a re-run may use a different model. Headless `-p` requires `--allow-all-tools`, so native ask/deny dialogs are unmeasured by design; the only configured permission signal is `--deny-tool shell(rm:*)`. |
| OpenCode | (a) Actions `.github/workflows/harness-opencode.yml` (localhost stub provider, NO key; checks out ref `harness-scorecard`; `opencode/runner.py`); (b) local real-binary `framework/scorecard/opencode-live-v1/runners/oc_run_one.py`, binary `/home/hatch/.opencode/bin`, localhost proxy port 8893, `localproxy/beam-free` | (a) None — stub. (b) Dummy `LOCALPROXY_API_KEY`; proxy + surrogate. Met. | `evidence/live-2026-11-04/opencode-live/`, sealed, 96 cells, Merkle `bbfb0edb…` — from route (b). | **The workflow path is stub-only and does not reproduce the sealed evidence.** It measures the permission engine + effects, never model choice. The real live path is local-only (binary + proxy outside the repo). No sandbox. |
| Goose | `framework/scorecard/goose-live-v1/runners/goose_run_one.py` + `matrix.py` (`goose run` headless, 3 profiles); binary `/home/hatch/workspace/tools/goose/goose` (verified present) | Dummy `OPENAI_API_KEY`; `beam-free` via localhost proxy port 8894 + surrogate. Met. | `evidence/live-2026-11-04/goose-live/`, sealed, 72 cells, Merkle `3b49c461…` | Binary + proxy outside the repo. No sandbox. Hardened/deny profiles are indistinguishable headless (the mode-gate abort fires before any tool rule is evaluated). No workflow. |
| Strands Agents | `framework/scorecard/live-agents-v1/runners/strands_run_one.py` (+ `strands_matrix.py`, `common.py`, `proxy.py`); local Python SDK in venv `~/workspace/.venvs/live-agents/bin/python` | Dummy key; proxy ports 8891/8892 + surrogate; models `beam-free` / `muse-spark-1.1`. Met. | `live-agents/` sealed bundle (part of the 480). | No policy by design (reference agent only — the measurement is of the framework's default, not of a guard). No workflow. Venv outside the repo. |
| LangGraph | `framework/scorecard/live-agents-v1/runners/langgraph_run_one.py`; same venv/proxy pattern | Dummy key; proxy + surrogate. Met. | `live-agents/` sealed bundle (part of the 480). | HITL `interrupt()` is the only gate. No workflow. Venv outside the repo. |
| CrewAI | `framework/scorecard/live-agents-v1/runners/crewai_run_one.py`; same venv/proxy pattern | Dummy key; proxy + surrogate. Met. | `live-agents/` sealed bundle (part of the 480). | Fail-open hooks, live-confirmed (non-`HookAborted` exceptions swallowed). No workflow. Venv outside the repo. |

Bundle-to-row mapping (for the record): Amp→`amp-live`; OpenClaw/Hermes/
Strands/LangGraph/CrewAI→`live-agents` (one bundle, 5 agents); Claude
Code (live)→`claudecode-live`; Muse Code→`musecode-v1` (+`musecode-n3-rerun`);
Omnigent→`omnigent-live`; Gemini→`gemini-live-full` (+`gemini-live`);
Codex→`codex-live-v1`; Copilot→`copilot-full` (+`copilot-live`);
OpenCode→`opencode-live`; Goose→`goose-live`. The README's "fourteen
signed bundles" count includes `adapters-v1`, which is the PAPER route
(120 decisions, 5 harnesses, no effects) — so 13 live bundles + 1 paper
bundle = 14.

## The three decision-only rows

| Harness | Live run? | What would unlock it |
|---|---|---|
| Claude Code (paper) | No live run on this row — superseded by the Claude Code (live) row above. The paper adapter (`adapters-v1` bundle) is history, not a gap. | Nothing. Keep as history. |
| Cursor | **No live run.** Manifest (`adapters/cursor.manifest.json`): real CLI not installed; evaluation pinned to vendor docs. "The CLI requires CURSOR_API_KEY/login — even read-only introspection of a live install needs auth." No `CURSOR_API_KEY` secret in the repo (verified: 4 secrets exist — `ANTHROPIC_API_KEY`, `COPILOT_GITHUB_TOKEN`, `GEMINI_API_KEY`, `MUSE_HEADLESS_KEY` — none is Cursor). No workflow, no runner. | Owner-only blockers: add `CURSOR_API_KEY` as a repo secret AND a paid Cursor plan (per owner context, parked). Then a runner + dispatch workflow still have to be written — none exists. Do not buy or create anything without Anish's word. |
| Pi | **No live run, by design.** Decision-only row 0.00: "Vendor-confirmed: no permission system by design." No adapter directory. | Nothing to build. A live run would measure nothing — the row is honest as 0.00. |

## How live runs are done today (the mechanism, end to end)

Three tiers, not one system:

1. **Dispatch-only GitHub Actions workflows (4 harnesses).**
   `.github/workflows/harness-copilot.yml`, `harness-gemini.yml`,
   `harness-opencode.yml`, `musecode-matrix.yml`, `musecode-smoke.yml`
   (plus `ci.yml`, which runs tests only — no live runs). All
   `workflow_dispatch` only, never push/PR. Secrets are passed via env
   on the runner step only and recorded by name only, never values.
   Records land as workflow artifacts and are pushed back to a branch
   (Copilot→its branch; Muse Code→`musecode-smoke`; Gemini→its branch).
   Two of the four do not reproduce the sealed evidence: Gemini-native
   fails outright, and OpenCode's workflow is stub-only by design.

2. **Local bespoke runners, published on main (9 packages).**
   `framework/scorecard/*-live-v1/` each carries its own runner(s):
   Amp (`run_one.py`, `matrix.py`), Claude Code (`run_series.py`),
   Codex (`run_one.py`, `run_matrix.sh`), Copilot (`runners/`),
   Gemini (`runners/`), Goose (`runners/`), live-agents (`runners/`),
   Muse Code (`v1_runner.py`, `approver.py`), Omnigent (`runners/`),
   OpenCode (`runners/`). Each was written fresh for its task — the
   docstrings say so ("fresh implementation for this task"). They share
   conventions (per-cell scratch git repo, fake fixtures only, stdin
   `/dev/null` + timeout so prompts fail closed, verdicts from witnessed
   tool calls + filesystem effects) but no shared code, no common CLI,
   and no common record schema — each writes its own `record.json`
   shape, normalized later at seal time. The live branches
   (`amp-live-v1`, `codex-live-v1-nov4`, … — 48 remote branches total)
   also hold copies; the `framework/scorecard/` packages are the
   published canonical copies per bundle provenance.

3. **Localhost proxy + dummy key + surrogate credential (the shared
   auth pattern for local runs).** The agent process holds only a dummy
   string (`dummy-local-only`, `LOCALPROXY_API_KEY=dummy-local-only`,
   …); a localhost proxy (ports 8891–8898) rewrites the model field and
   attaches the real credential via the dynamic-credentials surrogate,
   so no real credential appears in any file, log, or record. The
   live-agents proxy (`runners/proxy.py`) IS in the repo; the Claude
   proxy and the Gemini translator/proxy are NOT (local only); the
   Omnigent proxy is not shipped in its package.

**Sealing (common to all tiers).** `bundle.json` + Ed25519 signature
(`bundle.json.sig`) + Merkle root + inclusion proofs, verified by
`tools/verify_bundle.py` / `tools/check_bundle.py`. Cells carry
`source_path` + `source_sha256` of the original record bytes. Sealing
attests authorship and integrity, not independent witnessing (stated in
`evidence/live-2026-11-04/README.md`).

**Cost.** The Oct 23 campaign recorded spend per target (LangGraph
$0.0024, CrewAI $0.002, Strands ≈$0.02, Hermes ≈$0.07, Omnigent
≈$0.025, OpenClaw ≤$0.02 — cents). The Nov 4 bundles carry no spend
records. Actions minutes are free (public repo).

**Sandbox.** There is none anywhere: Docker is not installed on this
machine (`docker: command not found`), every live run records sandbox
"not-started", never a pass. Isolation is per-cell scratch dirs + fresh
sessions + fake fixtures on a shared host (local runs) or a fresh
Actions runner (workflow runs).

## Assessment — is the current way the best way?

Judged on the six criteria Anish asked for:

- **Reproducibility: weak.** The runners exist on main, but the
  binaries, venvs, logins, and two proxy scripts live in `~/workspace`
  outside the repo, and no install/setup script covers them
  (`tools/setup_harness.sh` fully verifies only the Codex oracle
  restore). No clean-checkout re-run has ever been attempted. What
  reproduces today is "same VM, same paths, same logins" — verified
  above: every local binary/path checked still exists on this machine,
  which is why re-runs work here and would not work on a fresh one.
- **Cost: cheap but untracked (Nov 4).** Oct 23 logged cents per
  target; Nov 4 bundles have no spend. Nothing in the pipeline would
  notice a run that suddenly cost 100× more.
- **Auth/secret handling: mixed.** Good: dispatch-only, secret confined
  to the runner step, name-only recording, dummy-key + surrogate keeps
  real credentials out of agent processes and records. Bad: no auth
  inventory anywhere; `ANTHROPIC_API_KEY`'s purpose is undocumented;
  Amp/Codex logins are undocumented; Cursor is blocked on a missing
  secret + paid plan.
- **Sealing of evidence: strong.** Signatures + Merkle roots + verify
  scripts, and the seal step is separate from the run step, so a runner
  bug cannot silently rewrite history. The one weakness is provenance
  text: see "Doc inconsistencies" below.
- **Per-harness isolation: partial.** Per-cell scratch + fresh sessions
  + fake fixtures is real isolation against cross-cell contamination,
  but there is no container boundary and no sandbox in any run; a
  harness that escaped its scratch dir would hit the shared host.
  Actions jobs are isolated per run; local runs are not.
- **Adding a new harness: weak.** `docs/EXTENDING.md` defines five
  artefacts (route dossier, adapter manifest, catalogue translations,
  route-assignment row, executable adapter + evidence) but no live-runner
  standard — no runner template, no workflow template, no auth pattern,
  no record-schema requirement. Every Nov 4 runner was a fresh
  implementation. Harness #15 means writing another bespoke runner plus
  another proxy arrangement from scratch.

Verdict: the current mechanism was the right way to measure 14 harnesses
in ~2 weeks under a deadline — ad-hoc runners + local proxies +
seal-after-the-fact got the evidence. It is not the best way to keep
measuring: it is unreproducible from a fresh checkout, unauditable on
auth, and every new harness reinvents the driver.

## Recommendation — what it should look like

Do NOT rewrite the Nov 4 runners. They are sealed evidence and part of
the bundles' provenance; leave them frozen. Build the replacement for
the NEXT measurement round (post-ceremony), and migrate harnesses one at
a time with the sealed bundles as regression oracles (a re-run through
the new framework must reproduce the sealed tallies within documented
variance).

1. **One live-runner framework, `tools/live_run.py`.** One CLI,
   per-harness driver plugins. Shared by all drivers: scenario loading
   (`framework/scorecard/scenarios-v1.json`), per-cell scratch +
   fixtures, timeout/fail-closed, ONE record schema (extend the
   check-run-bundle schema shape to live records — the attribution work
   on this branch already added `repeats`/`repeat_summary` there),
   proxy lifecycle (the runner starts and stops its proxy; never assume
   one is running), cost logging (tokens/spend per run, into the
   bundle), and sealing (bundle + sign in one command).
2. **A live manifest per harness** (`adapters/<key>.live.yaml`, or a
   section in the adapter manifest): binary + version pin + install
   recipe, auth method (secret name / subscription login / dummy+proxy),
   model pin (mandatory, observed per cell — not just requested),
   sandbox mode, dispatch workflow if any. `tools/setup_harness.sh
   status <harness>` becomes the readiness gate — it already has the
   shape (`status` prints the gap and exits 2); extend it to install
   and verify the live prerequisites instead of only the Codex oracle.
3. **Ship the missing pieces.** The Claude proxy, the Gemini
   translator, and the Omnigent proxy go in the repo (vendored, or
   replaced by one generic proxy with per-protocol modes). Rule: no
   runner may depend on a script that lives only in `~/workspace`.
4. **One auth inventory doc.** Every secret/login, where it lives, what
   it unlocks, expiry/rotation, owner. Document `ANTHROPIC_API_KEY`'s
   purpose or remove the secret. `CURSOR_API_KEY` only on Anish's word,
   with the paid plan.
5. **Actions as the canonical re-run path where possible** (Copilot,
   Muse Code, Gemini-native once its sandbox failure is fixed,
   OpenCode-real with a real model key). Local stays as a documented
   fallback with a machine-setup script. Subscription-login harnesses
   (Amp, Codex) can never run on Actions — local stays for them, with
   the login documented in the live manifest.
6. **Model pinning mandatory.** Record the model actually observed per
   cell. Fix Copilot (pin via `--model` if the CLI supports it, else
   record the model from stdout metrics) and Amp (unobservable — keep
   the caveat in every row, and fail the run if the CLI reports a
   different mode/version than pinned).
7. **Cost + sandbox honesty, kept.** Log spend per run (Oct 23 did
   this; Nov 4 didn't). Keep recording sandbox "not-started" honestly;
   a real per-cell container is a separate, larger project — don't
   pretend the scratch-dir discipline is a sandbox.

Trade-offs, stated plainly:

- Unified runner: refactor cost + risk of breaking record formats.
  Mitigation: keep the record schema identical, change only the driver
  layer; regress against the sealed bundles.
- Actions-first: free + isolated per run, but it cannot do
  subscription logins and needs a repo secret for every model key.
- Proxy-everywhere: uniform, and credentials never touch agent
  processes — but the proxy becomes a single point of failure that
  must itself be versioned and tested.
- Keeping the ad-hoc runners: zero refactor cost, but every new
  harness reinvents the driver and reproducibility stays "same machine
  only". That is the status quo, and it is how the next harness will
  also end up half-documented.

## Doc inconsistencies found (fix, don't ignore)

These are text staleness, not data problems — the sealed bundles and
their signatures are unaffected:

- `evidence/live-2026-11-04/amp-live/SUMMARY.md` is headed "(UNSEALED)"
  and the v4-scorecard build notes say "Amp live (Nov 4, UNSEALED)",
  but the bundle carries `.sig` files and a Merkle root in the sealed
  README. One of the two claims is stale.
- `musecode-n3-rerun/SUMMARY.md` says "not sealed" while the README
  lists it among the fourteen signed bundles with a Merkle root.
  Verify which is true before citing it either way.
- `.github/workflows/harness-copilot.yml` header says "the secret does
  NOT exist yet (2026-11-03)". `COPILOT_GITHUB_TOKEN` exists (created
  Nov 4, verified via the repo API). Stale comment.

## What I could NOT establish (UNKNOWN)

- Whether the `ANTHROPIC_API_KEY` repo secret backs the Claude live
  proxy. No workflow or runner references it; the runner uses a dummy
  key + surrogate. Settles it: ask the person who created the secret
  Nov 4, or check the proxy's credential source on the run machine.
- Which ChatGPT account the Codex CLI was logged into, and whether
  that login persists. No record in the repo. Settles it: the login
  state on the run machine (`codex` CLI auth status) plus a note in
  the codex package.
- What "ChatGPT subscription" means for the Amp CLI's model routing,
  and whether that subscription is still active. The repo's own words;
  the model is unobservable by design. Settles it: the Amp CLI's auth
  state on the run machine + a note in the amp package.
- What the Nov 4 runs cost. No spend records in the bundles. Settles
  it: cost logging in the next runner (recommendation 1).
- Whether any sealed bundle reproduces from a clean checkout. Never
  attempted. Settles it: one clean-machine re-run of a single harness
  (Copilot, the most Actions-native) and a tally diff against its
  sealed bundle.

## Sources (files read)

- `framework/scorecard/v4-scorecard.md`, `framework/scorecard/v4-cells.json`
  (the 14 live rows + 3 decision-only rows).
- `evidence/live-2026-11-04/README.md` + all 14 `bundle.json` provenance
  fields + all 14 `SUMMARY.md` files.
- `.github/workflows/ci.yml`, `harness-copilot.yml`, `harness-gemini.yml`,
  `harness-opencode.yml`, `musecode-matrix.yml`, `musecode-smoke.yml`.
- Runners: `framework/scorecard/*-live-v1/` packages (on main) and the
  `evidence/live-2026-11-04/*/runners/` copies; `copilot-cli/`,
  `gemini-cli/`; `adapters/cursor.manifest.json`.
- `docs/MEASUREMENT_ROUTES.md`, `docs/EXTENDING.md`,
  `evidence/live-campaign-2026-10-23/REPORT.md`.
- Repo secrets, verified live via the GitHub API (names + created dates
  only — no values): `ANTHROPIC_API_KEY`, `COPILOT_GITHUB_TOKEN`,
  `GEMINI_API_KEY`, `MUSE_HEADLESS_KEY` (4 total; no `CURSOR_API_KEY`).
- Local paths/binaries, verified present on this machine 2026-11-07:
  `~/workspace/amp-spike/package/amp`, `~/workspace/tools/goose/goose`,
  `/home/hatch/.opencode/bin`, `~/openclaw-stage4-install/…/openclaw.mjs`,
  `~/workspace/hermes-scratch-home/.local/bin/hermes`,
  `~/workspace/gemini-cli-cheaper/translator/proxy.py`,
  `~/workspace/{live-agents-v1,omnigent-live-v1,opencode-live-v1,goose-live-v1}/`,
  `~/workspace/.venvs/live-agents/bin/python`,
  `~/workspace/codex-live-v1-retry/restore/…/bin/codex`,
  `~/workspace/claudecode-fresh/node_modules/.bin/claude`.
  Docker: not installed (`docker: command not found`).
