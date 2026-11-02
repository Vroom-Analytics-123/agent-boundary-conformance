# Contributing to FinePrint

Contributions are welcome — measurements, adapters, catalogue translations,
docs, and fixes. The bar is the same as the project's own: everything
verifiable, nothing invented.

## Ground rules

- **Work on a branch, open a pull request.** Nothing goes straight to main.
- **Tests must pass:** `python3 -m pytest tests/ -q` (stdlib only, offline).
- **Sealed evidence is never edited.** A correction lands as a new bundle
  with its own Merkle root, never as a rewrite of a sealed file.
- **No invented scores.** Qualitative badges only; measured cells cite the
  bundle they came from. A cell you did not measure is "not tested."
- **Unknown is never allow.** Any code or doc that normalizes a no-match
  into an allow, a bypass, or a hole will not be merged.
- **Docs are concise and visual-first.** Text explains what the visual
  cannot; if a paragraph can be a diagram, make it a diagram.

## Adding a harness or target

Follow [docs/EXTENDING.md](docs/EXTENDING.md): dossier + manifest first,
draft translations in `docs/catalogue/translations-draft/`, measurement
route assigned by provenance (vendor-confirmed / reconstructed / no paper
surface — never a rank). A target with no decision surface gets the
"no paper surface" route and an instrumented-reference-agent design, not a
paper verdict.

## Reporting a problem

Use the issue templates. A good bug report names the command, the policy,
the harness + version, and what the native checker actually decided —
not just what you expected.
