# FinePrint fix-skill — Codex (PROTOTYPE / DRAFT)

**Status: PROTOTYPE / DRAFT. Not published. Not listed in any marketplace.
Not tested in a live agent session.** The rules in this package were
exercised against the pinned Codex 0.149.0 native policy checker
(`codex execpolicy check`) during assembly — see `probes.md` for what was
run and what it returned. Nothing here certifies any setup as secure.

This package is the first prototype of FinePrint's fix delivery form: a
measurement finding, paired with the drafted clause that closes it,
packaged as an installable skill so the corrected policy travels with the
user's agent setup. FinePrint is the inspector who drafts fixes, never the
enforcer — the owner decides whether to adopt them.

| File | Contents |
|---|---|
| `SKILL.md` | The skill itself: findings, evidence classes, installable clauses, re-verification, versioning, honest boundary |
| `files/codex-execpolicy-hardened.rules` | Installable execpolicy rules: baseline + sealed Day-5 fix (Section A) + drafted enumeration extensions (Section B) |
| `files/codex-protected-path.rules` | Protected-path rules with the FP-003 token-prefix trap documented; worked example `/records/health` |
| `files/codex-approval-posture.toml` | Approval/sandbox config posture — the compensating control for the gaps rules cannot close (FP-009, FP-012) |
| `probes.md` | The conformance probes to re-run after install, with expected and assembly-observed decisions |

Target choice, in one line: Codex carries the richest **verified**
material in the repo — a vendor-confirmed Decision-layer route, a 41-case
measured corpus, a sealed post-fix bundle, and one already-completed
finding→fix loop (the Day-5 fix) to model the form on. The six Wave A
targets (Omnigent, LangGraph, Strands, CrewAI, Hermes, OpenClaw) are
design-stage and UNMEASURED; a fix-skill built on paper findings would have
to label every clause as unverified, so they are not this prototype's
target.
