# Fix draft — OpenClaw: argv granularity, allow-always availability, and approval-route disclosure

**Status:** DRAFT (Stage 4 live findings, 2026-10-23 — not yet reviewed, not
submitted upstream)
**Target:** OpenClaw 2026.10.6 (fe06181), `github.com/openclaw/openclaw`
**Scope note:** OpenClaw is a gateway/runtime, not a coding agent; this draft
concerns only its native exec-approval boundary (`tools.exec.*`, host
exec-approvals, `tools.allow`/`tools.deny`).

## Finding 1 — Allowlist granularity is the binary, never argv (live-confirmed)

**Evidence (live):** with a path-only allowlist entry `pattern: "/usr/bin/rm"`
(no `argPattern`), both `rm -fr <target>` and `rm --recursive --force <target>`
executed with **zero** approval requests under `security=allowlist,
ask=on-miss`. The operator CLI itself renders such entries' args column as
"any args". Any argv distinction a policy author cares about (recursive? force?
which operands?) is invisible to the configured decision.

**Nuance:** 2026.10.6 *does* support an optional `argPattern` (ECMAScript regex
over argv excluding argv[0]) on hand-authored entries — but nothing in the
documented operator flow surfaces it: `approvals allowlist add` creates
path-only entries, the ask flow cannot mint arg-restricted entries, and the
docs' mental model ("allow a binary = allow the binary") is what operators
will actually deploy.

**Proposed fix (either or both):**

1. **Exec-policy extension sketch** — make argument scoping a first-class,
   visible part of an allowlist entry instead of an undiscovered field:

   ```jsonc
   // exec-approvals (SQLite store, exec_approvals_config)
   {
     "pattern": "/usr/bin/rm",
     // NEW: declarative argv constraints, evaluated per segment
     "argvPolicy": {
       "denyFlags": ["--recursive", "-r", "-R"],   // any match → treated as allowlist MISS (falls to ask)
       "denyOperandsUnder": ["/"],                  // operands outside listed roots → miss
       "maxOperands": 8
     }
   }
   ```

   Semantics: an entry matches only if the pattern matches **and** every argv
   constraint holds; constraint failure degrades to the existing on-miss path
   (ask), never to silent allow. This preserves fail-closed behaviour and the
   existing "stricter of tools policy vs host approvals wins" composition.

2. **Doc disclosure (minimum bar)** — state plainly in the exec-approvals docs:
   *"A path-only allowlist entry allows the binary with ANY arguments
   (`rm` ⇒ `rm -rf /`). If you need argument restrictions, hand-author an
   `argPattern`; the CLI and the approval flow do not create one for you."*

## Finding 2 — "allow-always" is advertised but was never offerable (live)

**Evidence (live):** the effective policy displays
`allowedDecisions: [allow-once, allow-always, deny]`, yet **every** witnessed
`exec.approval.requested` (6/6: `touch`, `rm -rf`, `echo` — benign and
destructive, file and non-file operands, CLI-originated Gateway sessions)
carried `allowedDecisions: ["allow-once","deny"]` and
`unavailableDecisions: ["allow-always"]`, and an `allow-always` resolve was
refused: `APPROVAL_ALLOW_ALWAYS_UNAVAILABLE`. Vendor code collapses
allow-always to one-shot whenever the persistence decision is one-shot
(mutable-file-operand commands are forced one-shot; no tested command reached
pattern persistence). Operators reading the policy display will believe
persistence exists where, on this surface, it does not.

**Proposed fix:** (a) include the one-shot reason in the request payload
(e.g. `unavailableDecisionReasons: {"allow-always": "mutable-file-operand"}`)
so clients can explain the absence instead of silently omitting the button;
and (b) make the effective-policy display (`approvals get`, `exec-policy show`)
report the decisions that will actually be offered per surface, or annotate
allow-always as conditional. At minimum, document the one-shot rules (mutable
file operands, inline-eval/shell forms, pattern-persistence preconditions)
next to the `ask` modes.

## Finding 3 — Ask without a connected approval client is a silent deny (live)

**Evidence (live):** with `tools.exec.mode="ask"`, `askFallback=deny`, and **no**
approvals-capable client connected, CLI-originated runs produced no deliverable
approval request; the agent was told inline that "headless runs cannot wait for
interactive execution approvals" and the command never ran. The same runs with
a connected operator client paused properly and were approved/denied with full
effect separation. The dependency — *an approval pause exists only while a
Control UI / app / API client with `operator.approvals` is connected* — is
operationally crucial and easy to miss: an operator can believe commands are
"awaiting approval" when they were already denied.

**Proposed fix:** document the approval-route requirement alongside
`askFallback`, and surface the no-route denial distinctly in session records
(reason `no-approval-route` is already computed internally — persist it where
operators look).

## Observations (no fix proposed here)

- **`tools.deny` precedence works as documented, and fails closed:** deny over
  allow excluded `exec` per-call (OC-D2), and when deny emptied the callable
  set the Gateway refused the turn rather than running tool-less (OC-D1).
- **Approvals storage moved to SQLite** (`state/openclaw.sqlite`,
  `exec_approvals_config`) at 2026.10.6; third-party docs (including ours)
  still describe `~/.openclaw/exec-approvals.json`. Worth an explicit docs
  note/migration callout upstream.
- **Sandbox posture vs runtime divergence:** `sandbox explain` under
  `mode: "all"` reports a sandboxed session, but session provisioning fails
  outright when no Docker daemon exists — the claim and the capability part
  company until the first session starts. A startup-time capability check
  (fail fast at Gateway boot, or downgrade the explain output) would close
  the gap.
- **Elevated gating:** with `tools.elevated.enabled=false`, `sandbox explain`
  reports elevated failures `[gate: enabled]` — gating is legible at the
  configured layer; elevated exec itself was out of scope for this stage.

## Evidence

`evidence/live-campaign-2026-10-23/openclaw/` — `RESULTS.md` (narrative +
verbatim records), `runs.json` (per-case A2/A3/E1–E2), `records/` (Gateway
event streams, policy inspectors, snapshots, outside scan). Draft only;
nothing here has been sent upstream.
