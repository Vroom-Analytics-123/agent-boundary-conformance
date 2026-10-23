# Catalogue Commons — design

The local-first core of the founder-directed (Oct 22, 2026) product:
**build an invariant catalogue, let people add to the catalogue and create
their own, create invariants for people, and test their harness against
them regularly and at every new deployment.**

This document describes the three-layer catalogue, the contribution flow,
the check runner (`tools/fineprint_check.py`), the deployment-gate mode,
and the local-first boundary — what runs on your machine today, and what
the future hosted layer adds (roadmap, not built).

## The three layers

```
core catalogue          docs/catalogue/catalogue.json (16 patterns, v1.0.0)
      + domain packs    docs/catalogue/domain-packs/*.json   (Phase-2 scope)
      + org overlay     your machine only, private:true       (never leaves)
      = composed pack   one annotated entry list per run
```

Every composed entry carries `source_layer` (`core` | `domain` | `org`) and
a `private` flag (org → true). The composition report (per run,
`composition.json`) records counts, overrides, and rejected duplicates.

- **Core** is the shared commons. Changes go through the maintainers.
- **Domain packs** (health, fintech, SaaS — Phase-2 scope) are curated
  overlays in the same entry shape. Duplicate ids across packs are
  rejected (fail closed).
- **Org overlays** are yours. An overlay id (`ORG-<org>-<suffix>`) may
  intentionally *override* a core/domain id — your private version wins
  for your runs, and the override is recorded. Overlay files live in
  `catalogue-contrib/org-overlays/` (gitignored) or anywhere else on your
  machine. **Never commit them.**

## Contribution flow

`catalogue-contrib/` holds the format:

- `contrib.v1.schema.json` — the normative JSON Schema for an entry. It
  extends the `catalogue.json` entry shape (`id`, `intent`, `parameters`,
  `expected_decision`, `probe_families`, `provenance`, …) with contribution
  metadata: `author`, `licence`, `contribution_kind`
  (`community` | `org-overlay`), `private`, `submitted_utc`.
- `CONTRIBUTING.md` — how to propose an entry and the review bar.
- `examples/` — two worked, schema-valid examples: a community entry
  (`FP-COMM-001`) and an org-overlay entry (`ORG-ACME-001`, `private:true`).

The repo is stdlib-only, so the schema's executable enforcement lives in
`tools/catalogue_loader.py::validate_contrib` (each check cites the schema
property it enforces). Validate before sending:

```
python3 tools/catalogue_loader.py --validate-contrib <entry>.json
```

### The review bar (non-negotiable)

1. **No entry without probes** — an invariant without probes is a wish.
2. **Measured before claimed** — new entries arrive `UNMEASURED`. `MEASURED`
   is granted by maintainers only after the expectation runs on the pinned
   vendor checker; the loader rejects `MEASURED` without measured provenance +
   evidence refs.
3. **Provenance required** — no anonymous invariants.
4. **Every `<slot>` in a probe must be a declared parameter.**
5. **Dual-verdict honesty** — probes that expect `unknown` are unresolved
   intent at the Decision layer, never satisfied protections.

## The check runner (product wedge)

```
python3 tools/fineprint_check.py --harness codex \
    --policy fixtures/policies/default.rules \
    [--domain-pack pack.json ...] [--org-overlay org.json] \
    [--bindings bindings.json] [--only FP-001,FP-002] \
    [--out run-dir] [--label NAME] [--public-only] [--sign] \
    [--baseline previous-bundle.json]
python3 tools/fineprint_check.py --list-adapters
```

One command takes an **invariant pack** (the three-layer composition), a
**harness adapter**, and a **policy config**; runs every probe; and emits
into `--out`:

| file | contents |
|---|---|
| `bundle.json` | sealed check-run evidence bundle (`check-run-bundle.v1`): per-probe findings, per-invariant dual verdicts, Merkle-sealed, claim scope = MEASURED entries only |
| `scorecard.json` / `scorecard.html` | the scorecard: per-invariant dual verdicts with per-probe detail, unknown-kind breakdown, reproducibility footer |
| `bindings.json` | the parameter bindings the run used |
| `composition.json` | the pack composition report |
| `baseline-diff.json` | only in `--baseline` mode |

**Parameter bindings.** Slots bind from `--bindings` (per-invariant ids,
plus `__default__`), falling back to the catalogue entry's `example`
values. A required slot with no binding anywhere fails closed — the
runner never invents one. List values splice into argv as multiple
tokens.

**Expectation encoding.** A probe family's `expected` list is either
*positional* (`len(expected) == len(probes) > 1`, e.g. FP-012's
`[allow, forbidden]`) or *alternatives* (the probe passes when its actual
decision is any member, e.g. FP-002's `[prompt, forbidden]`).
`unmatched-reported-as-unknown` normalizes to `unknown` (INV-005).

**Dual verdicts, per invariant** (see `tools/check_scorecard.py`):

- *measurement_validity*: PASS (every probe ran and matched expectation) /
  FAIL / NOT_REPRODUCED.
- *intent_coverage*: SATISFIED only when every probe's actual decision is
  `forbidden`/`prompt` (restrictive) — an unsanctioned `allow` is
  NOT_SATISFIED; any `unknown` is UNRESOLVED. A correctly reported unknown
  is measurement PASS (when expected) but **never a satisfied invariant**.
- The scorecard's **claim scope** covers MEASURED entries only;
  UNMEASURED entries are exploratory (probes ran, no claim).

**The deployment gate consumes `bundle.json`.** It is sealed
(Merkle root over canonical-JSON findings; `verify` via
`python3 tools/check_bundle.py --verify bundle.json`) and pins the
harness, policy sha256, pack composition sha256, and bindings sha256 —
so a gate decision is reproducible.

## Deployment-gate mode (`--baseline`)

```
python3 tools/fineprint_check.py --harness codex --policy <new-policy> \
    --baseline <previous-bundle.json> --out gate-run/
```

The fresh run is diffed against the sealed baseline. Reported:

- **REGRESSIONS** — intent coverage rank decreased (SATISFIED →
  UNRESOLVED/NOT_SATISFIED, UNRESOLVED → NOT_SATISFIED); a protective
  decision flipped to `allow`/`unknown` on a restrictive invariant
  (even when the aggregate rank didn't move); an invariant present in
  the baseline but dropped from the fresh run.
- decision flips (informational), improvements, added/dropped invariants.

**Exit codes:** `0` = run ok, no regressions · `1` = usage/runtime error ·
`2` = regressions found (gate BLOCKED). The convention is documented in
`--help` and demonstrated under `evidence/demo-check-2026-10-22/`.

## Adapter contract

`tools/check_adapters.py` registers adapters. Each provides
`check_environment()` and `run_probe(argv, policy)` returning
`{actual, matched_rules, raw, note, layer, error}` with `actual` in the
shared vocabulary (`forbidden` | `prompt` | `allow` | `unknown`).

| adapter | measurement route | route |
|---|---|---|
| `codex` | vendor-confirmed | pinned native checker (`codex execpolicy check`) via `tools/pin.py` — fail closed if the pinned binary is unavailable |
| `claude-code` | reconstructed | documented-semantics evaluation engine (`adapters/claude-code/evaluate.py`); evidence class "reconstructed evaluation (never interrogated)" |

Other reconstructed-route engines (cursor, gemini-cli, opencode) expose
different `evaluate()` signatures today; they join the registry when a
conformant shim exists — a wrong shim is worse than no adapter.
Reconstructed-route runs measure the documented-semantics engine against
the pack's expectations: divergences from codex-measured expectations are
engine-vs-checker differences, not conformance verdicts, and the scorecard
labels them as such.

## The local-first boundary

Everything above runs on your machine, with no accounts, no network
(except the sandbox's), and no publishing. In particular:

- **Org overlays never leave the machine.** Default output flags private
  entries (`private: true`) for your own use; `--public-only` strips them
  *before sealing* — the bundle is re-sealed over public findings only,
  so no private content leaks through hashes, ids, bindings, or the
  reproducibility recipe (the overlay path and private ids are scrubbed
  from it too). This privacy property is unit-tested end-to-end.
- **Nothing is executed.** Probes only ask the harness for its ruling
  (`observed_effect` is NOT_TESTED for every probe).
- **Sealed bundles are never rewritten.** Dual verdicts live in the
  reporting layer; the bundle's Merkle root is untouched.

### What the future hosted layer adds (roadmap, not built)

Recurring scheduled checks, deployment webhooks that consume gate mode,
and a review queue for community submissions. It does not change the
entry format, the review bar, or the local-first boundary: the hosted
layer can never see your overlay, because your overlay never leaves
your machine.

## Known limitations (honest)

1. **Probe underspecification.** Core catalogue probe templates reference
   slots outside the entries' declared parameter lists, and don't record
   oracle flags (e.g. FP-011's `/nonexistent/rm` expectation was measured
   with `--resolve-host-executables`). The runner requires explicit
   `--bindings` for undeclared slots (recorded, never invented) and runs
   catalogue probes verbatim otherwise; mismatches surface as FAIL/
   UNRESOLVED rows, which is the gate doing its job. Per-probe execution
   hints are roadmap.
2. **One policy per run.** Catalogue probes were measured across policies
   (e.g. FP-016's `ls /records/health` allow was measured under
   `protected_records.rules`, not the sample `default.rules`). Cross-policy
   probes surface as expectation mismatches; per-probe policy binding is
   roadmap.
3. **Post-fix bookkeeping.** FP-001/FP-010 variant probes whose catalogue
   expectations were frozen at `unknown` (Day-5 fix) now measure
   `forbidden` — expectation FAILs where the oracle is *more* protective.
   Intent adjudication treats these as satisfied-protection, not
   regressions.
4. **Reconstructed-route expectations.** The core pack's expectations
   are codex-measured; running them against a reconstructed-route engine
   yields informative divergences, not conformance verdicts.
