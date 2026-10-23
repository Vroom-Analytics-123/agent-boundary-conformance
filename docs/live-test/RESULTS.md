# Paper-vs-live wave — results (2026-10-22)

**Wave:** `live-test-2026-10-22` · FinePrint (agent-boundary-conformance).
**Pre-registration:** `docs/live-test/PREREGISTRATION.md` — locked
2026-10-23T00:59:36Z, committed as `ae8eb37` **before any case execution**.
**Results written:** 2026-10-23.
**Status: BLOCKED — valid terminal state for all nine harnesses**
(pre-registration §6: "if the §3 gate fails for a harness, stop for that
harness after this pre-registration and record precisely the missing auth
artifact").

## 1. What happened

No live case was executed for any harness. The runnability gate
(pre-registration §3) failed at **route (a)** for all nine harnesses and
at **route (b)** for all nine harnesses:

- **Route (a) — local/open model provider already in the environment:**
  fails everywhere. No `ollama` binary; nothing listening on 11434 or
  1234; `OLLAMA_HOST` / `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` all
  unset (REPRO — observed).
- **Route (b) — vendor offline/demo mode that genuinely executes tools:**
  fails everywhere. The only no-auth agent-ish modes found are
  non-executing: Muse Code's `--provider echo` makes no tool calls
  (assessment-established); Amp's no-auth surface is `permissions test`,
  a paper oracle, not an agent (`amp --no-tui` threads require a logged-in
  account — verified read-only via `--help` in a scratch HOME).

API-key presence sweep (names only, values never read):
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`,
`COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`, `META_API_KEY`,
`MODEL_API_KEY`, `AMP_API_KEY`, `OPENCODE_API_KEY`, `CURSOR_API_KEY`,
`ZEN_API_KEY` — **all absent** (REPRO). Auth files `~/.codex/auth.json`,
`~/.claude`, `~/.amp`, `~/.config/muse`, `~/.copilot` — **all absent**
(REPRO). `~/.cursor/cli-config.json`, `~/.gemini/projects.json`,
`~/.config/opencode` exist but carry no credentials (editor config /
empty project trust / empty directory).

No workaround was attempted (pre-registration §3: "no workarounds, no
credential improvisation, no account creation"). No install was
performed to manufacture a route. Per the wave instructions, Codex was
not re-probed — its blocked entry cites the locked pilot.

## 2. Per-harness paper-vs-live matrix

Paper verdicts are the recorded wave verdicts, cited — never re-derived
in this wave (pre-registration §2). Live status is `blocked` for all.

| Harness | Paper grade | Paper evidence basis (cited) | Live status | Precise blocker (the missing auth artifact) |
|---|---|---|---|---|
| Codex (codex-cli 0.149.0) | A · Oracle | Pilot PREREGISTRATION §4 (16 locked expectations) + post-fix 41-case corpus (docs/harness-testing-2026-10-22.md) | blocked | OpenAI model auth: `~/.codex/auth.json` absent, `OPENAI_API_KEY` absent — pilot-established, 0/16 run, not re-run |
| Amp (0.0.1792680614-g8973a3) | A · Oracle | Spike probes P-01…P-13 (`amp permissions test --json`, byte-identical ×2; docs/amp-spike-2026-10-22.md) | blocked | Amp account auth: no `amp login` session exists; `permissions test` is offline-only (paper), `--no-tui` threads require login |
| Claude Code (2.1.307) | B · Manual | adapters/claude-code/results.json (21 public + 6 protected cases; engine 85/85 tests) | blocked | Anthropic API key (`ANTHROPIC_API_KEY` absent) or logged-in `claude` OAuth session; CLI not installed |
| Cursor (2026.10.19-6bbf2c4) | B · Manual (Allowlist only) | adapters/cursor/results.json (27 public cases; engine 38/38 tests); Auto-review mode unevaluatable | blocked | Cursor account login; CLI not installed |
| Gemini CLI (0.65.0) | B · Manual | adapters/gemini-cli/results.json (21 public + 6 protected; engine 33/33 tests) | blocked | Gemini/Google API key (`GEMINI_API_KEY`/`GOOGLE_API_KEY` absent) or Google OAuth login; CLI not installed |
| OpenCode (1.19.3, 1.x) | B · Manual | adapters/opencode/results.json (27 public cases; engine 43/43 tests) | blocked | Any configured model-provider credential (e.g. OpenAI/Anthropic key or OpenCode Zen); CLI not installed |
| Copilot CLI (1.0.103) | B · Manual (T2-config) | adapters/copilot-assessment.md (assessment only — no corpus verdicts emitted) | blocked | GitHub login + active Copilot subscription (the `/login` wall) |
| Pi (earendil-works/pi) | C · No paper | No rule surface by design — README: no built-in permission system (docs/FRAMEWORK.md) | blocked | Model endpoint + credentials; live is the only possible evidence for Pi and it is unreachable without them |
| Muse Code (1.4.11) | C · No paper | No deterministic decision oracle (adapters/muse-code-assessment.md); profiles are select-never-create | blocked | Meta developer account (dev.meta.ai sign-in) or `MODEL_API_KEY`; `--provider echo` disqualified (no tool calls) |

Cases run: **0 of 12** for every harness (0 of 108 total). No sandbox
was created. No case command was proposed to any agent. Observed effects:
none — `NOT_TESTED` for all rows. Agreement classes: `not-evaluated`
(blocked precedes execution).

**Per-case tables:** none — required only for harnesses that ran, and
none did. The 12 locked cases in the pre-registration stand ready for
the first founder-auth run, unchanged.

## 3. Headline finding (the disagreement that this wave DID measure)

No paper-vs-live agreement class could be evaluated — the live side is
empty for all nine harnesses. What this wave measured, honestly and at
REPRO grade, is the **binding constraint on the entire online program**:

> Every harness's live agent loop is auth-walled in this environment,
> and the wall is the account/login/key itself — not a missing CLI, not
> a missing feature flag, not a technical oracle absence.

The Codex pilot found this first (0/16, blocked on model auth); this
wave generalizes it: **9/9 harnesses blocked-by-auth, each with its
specific missing artifact named in the matrix above.** This is the same
field finding the empirical wave already reported for Copilot
("account walls are the binding constraint on live testing"), now
measured across the full harness set under a locked protocol. It is a
negative result, and it is publishable: FinePrint's online method works
up to the wall — the wall is environmental, not methodological.

Consequences for the dual verdict: `measurement_validity` for every
live row = NOT_MEASURED; `intent_coverage` at the observed-effect layer
= UNRESOLVED for all 12 cases on all 9 harnesses. Nothing about any
harness's runtime behaviour (approval decisions, sandbox enforcement,
observed effects) was measured in this wave, and no such claim is made.

## 4. Containment notes

- No per-harness sandbox was created (the job stopped at the §3 gate
  before §4 setup for every harness).
- No case command was executed; no file was created, modified, or
  deleted by the wave anywhere. The pre-registration §4 rule-8
  post-run scan is trivially satisfied: there was no run window.
- No network I/O beyond read-only `--help`/presence probes; no
  credentials created, read, or passed; no real user files involved at
  any point.
- Nothing was published, sent, or submitted. No outreach of any kind.
- The read-only probes in pre-registration §3 (env survey, amp
  `--help` in a scratch HOME) are the only commands executed; they
  launched no agent session and touched no target.

## 5. Claims and evidence classes

- The **runnability-gate facts** (§1) are REPRO: direct observations of
  this environment (ports, binaries, key names, auth-file absence,
  amp help surface). They are environment facts, not claims about any
  harness's approval or sandbox behaviour.
- The **12 locked cases and 9 pinned configs** (pre-registration §§2, 5)
  are HYPOTHESIS-grade until a founder-auth run executes them: declared,
  committed, not executed.
- The **paper verdicts** referenced in §2 are the recorded wave
  verdicts at their stated evidence classes (REPRO for oracle runs,
  T2-evaluation for config engines, assessment-only where no corpus
  was evaluated) — cited, not re-measured here.
- **No REPRO claim is made about any runtime behaviour** (approval
  decisions, sandbox enforcement, or observed effects). Any citation of
  this wave must say "blocked at the runnability gate — no live cases
  executed", never imply measured runtime outcomes.
- Wave evidence JSON: `docs/live-test/evidence-live-wave-2026-10-22.json`
  (standalone; `signature_state: "unsigned"`, `witness_state:
  "unwitnessed"`).
- **Config-pinning caveat:** when a founder-auth run does execute, its
  live results hold for the pinned runtime config only (pinned version,
  pinned approval config, pinned workspace, pinned model/provider) —
  per pre-registration §5.

## 6. What would unblock this wave

Founder-supplied auth, per harness, used only for the contained 12
cases under the locked pinned configs — zero changes to the
pre-registration needed:

| Harness | What unblocks it |
|---|---|
| Codex | OpenAI model credentials for the pinned 0.149.0 binary (`~/.codex/auth.json` or `OPENAI_API_KEY`) |
| Amp | One `amp login` session (account auth), then `amp --no-tui` threads in the sandbox |
| Claude Code | `ANTHROPIC_API_KEY` or a logged-in `claude` session at 2.1.307 |
| Cursor | A logged-in Cursor account (Allowlist mode), CLI at 2026.10.19-6bbf2c4 |
| Gemini CLI | `GEMINI_API_KEY` (or Google OAuth) at 0.65.0 |
| OpenCode | Any configured provider credential in opencode.json at 1.19.3 |
| Copilot CLI | GitHub login + active Copilot subscription at 1.0.103 |
| Pi | A model endpoint + key Pi can use |
| Muse Code | Meta developer account or `MODEL_API_KEY` at 1.4.11 |

Until then, the paper side (A/B grades) remains the measured evidence
and the live side remains UNRESOLVED — stated plainly, not papered over.

## 7. Deviations

None. The pre-lock driveability probes are disclosed in pre-registration
§3; they preceded any case execution. No case, config, or containment
rule changed after the lock.
