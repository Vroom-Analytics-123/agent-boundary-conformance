# Contributing to the FinePrint Invariant Catalogue

The catalogue is a commons: the core catalogue (`docs/catalogue/catalogue.json`,
16 patterns) is the shared base, and anyone can propose additions — a new
protective invariant, an evasion family, a metrology probe — or keep a private
org overlay for their own checks. This file is the whole review process.

## The three lanes

| Lane | Who | Where it lives | Visibility |
|---|---|---|---|
| **Community** | anyone | submitted as one JSON file per entry, validated against `contrib.v1.schema.json` | public, CC-BY-4.0 (or your stated licence) |
| **Org overlay** | your team | `catalogue-contrib/org-overlays/` (gitignored — see below) | **never leaves your machine** |
| **Domain pack** | maintainers / working groups | `docs/catalogue/domain-packs/` (Phase-2 scope: health, fintech, SaaS) | public |

## How to propose a community entry

1. Copy `catalogue-contrib/examples/community/FP-COMM-001-privilege-escalation-gate.json`.
   It is a complete, schema-valid entry — replace its content, keep its shape.
2. Give it an id of the form `FP-<suffix>` (e.g. `FP-COMM-001`). Ids must be
   unique across the composed pack.
3. Validate locally before sending:
   `python3 tools/catalogue_loader.py --validate-contrib <your-file.json>`
   Exit 0 = schema-valid. Anything else = fix the listed errors.
4. Send the file to the maintainers (channel TBD at hosting time; for now,
   the review happens wherever the repo's review happens).

## The review bar (non-negotiable)

An entry is accepted only if ALL of these hold:

1. **No entry without probes.** `probe_families` must contain at least one
   family with at least one probe. "An invariant without probes is a wish."
2. **Measured before claimed.** New entries arrive `UNMEASURED`. `MEASURED`
   is granted by maintainers only after the expectation runs against the
   pinned oracle (Codex T1 native, `codex-cli 0.149.0`) — never on the
   contributor's say-so. A contribution that sets `measurement_status:
   MEASURED` must carry `provenance.kind: measured` with `measured_on`
   naming the harness + version, plus `evidence_refs`; the loader rejects
   anything weaker.
3. **Provenance required.** Every entry states where it came from
   (`provenance.kind` + `detail`): a doc URL with retrieval date, a paper,
   an incident, or an explicit hypothesis. No anonymous invariants.
4. **Slots referenced by probes must be declared.** Every `<slot>` in a probe
   argv template must be a declared `parameters` slot (loader-enforced).
5. **Dual-verdict honesty.** An entry whose probes expect `unknown` (e.g.
   variant/wrapped families) is understood to be *unresolved intent* at the
   rules layer — the scorecard will never display it as a satisfied
   protection.

Maintainers accept or reject with a one-line reason recorded next to the
entry. Rejections are not personal: the common reasons are missing probes,
missing provenance, and claims that outrun the measurement.

## Org overlays (private by construction)

An org overlay is a JSON file in the same entry shape, with
`contribution_kind: "org-overlay"` and `"private": true`:

- Keep it in `catalogue-contrib/org-overlays/` (gitignored) or anywhere else
  on your machine. **Never commit it, never attach it to an issue, never
  paste it into a hosted form.**
- An overlay id (`ORG-<org>-<suffix>`) may intentionally override a core or
  domain id: the org's private version wins for that org's runs, and the
  override is recorded in the run's composition report.
- Run checks with it:
  `python3 tools/fineprint_check.py --harness codex --policy <rules> --org-overlay catalogue-contrib/org-overlays/my-org.json`
- The check runner strips private entries from every *public* artifact.
  Default output includes them (flagged `private: true`) for your own use;
  `--public-only` emits artifacts with zero org content — bundles are
  re-sealed over the public findings only, so nothing private leaks through
  hashes either. This privacy property is unit-tested
  (`tests/test_catalogue_commons.py`).

## What the future hosted layer adds (roadmap, not built)

Today everything above runs locally. The hosted layer — when the entity
exists to run it — adds: recurring scheduled checks, deployment webhooks
that consume the gate mode (`--baseline`), and a review queue for community
submissions. It does not change the entry format, the review bar, or the
local-first boundary: the hosted layer can never see your overlay because
your overlay never leaves your machine.
