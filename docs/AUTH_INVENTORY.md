# Auth inventory — live-runner framework

Names ONLY. No values are recorded here, in any manifest, or in any
log the framework writes. "Repo secret" means a GitHub Actions
secret on `Vroom-Analytics-123/agent-boundary-conformance`
(verified by name + creation date via the API; values are not
readable). "Owner login" means an interactive subscription login
on the owner's machine or account — it cannot be verified
non-interactively and is always a readiness gap in `status`.

## Repo secrets (verified 2026-11-08)

| Secret | Created | Purpose | Used by |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | 2026-11-04 | Anthropic API access (Claude Code runs that use the API rather than the subscription login) | claude-code (when API-routed) |
| `COPILOT_GITHUB_TOKEN` | 2026-11-04 | Fine-grained PAT on vroomanalytics123; Copilot CLI auth | copilot-cli |
| `CURSOR_API_KEY` | 2026-11-08T00:28:27Z | Cursor user API key; print mode (`-p`) rejects OAuth-only sessions, so this is the ONLY headless auth | cursor |
| `GEMINI_API_KEY` | 2026-11-04 | Gemini API access | gemini-cli |
| `MUSE_HEADLESS_KEY` | 2026-11-02 | Muse Code headless auth | muse-code |

## Subscription logins (owner's accounts, not secrets)

| Login | Purpose | Used by |
|---|---|---|
| Anthropic subscription login | Claude Code CLI when subscription-routed (proxy passes through to cheaperinference; the agent holds no credential) | claude-code |
| ChatGPT subscription (mode medium) | Amp CLI | amp |
| ChatGPT subscription or API key — NOT ESTABLISHED | Codex auth method is not recorded in the Nov 4 run notes; settle from the codex-live-v1 package notes before any re-run | codex |
| Cursor paid plan | The `CURSOR_API_KEY` above is a user API key from the Cursor dashboard; whether the underlying plan covers CLI use is NOT confirmed by the key's presence — the dispatch run shows AUTH_FAILED if it does not | cursor |

## Dummy + localhost proxy (no real credential in the agent env)

| Method | Purpose | Used by |
|---|---|---|
| Dummy key + `tools/live_proxy.py serve` (cheaper arm) | The proxy rewrites the model and attaches the real credential server-side via the surrogate helper; agents hold no credentials | openclaw, hermes, strands, langgraph, crewai, opencode, goose |
| Dummy key + `tools/proxies/omnigent_proxy.py` | Same pattern, Omnigent's proxy (adds `/responses`) | omnigent |

## Scoped exceptions on anishk123@gmail.com

The hard rule stands: nothing on that account without Anish's
explicit approval for that specific use. The only live exception
relevant here: **Nov 3 — Gemini harness auth ONLY** (Anish's
explicit approval). It does not extend to any other harness.

## What is missing

- `CURSOR_API_KEY` — present since 2026-11-08 (see above).
- Codex auth method — UNKNOWN (see table).
- No other harness needs a secret that is not already listed.
  If a future driver needs one, add it here by NAME ONLY and name
  the owner step that creates it; never paste a value.
