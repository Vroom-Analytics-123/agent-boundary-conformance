#!/usr/bin/env python3
"""FinePrint catalogue loader: compose core + domain packs + org overlay.

Three layers (docs/CATALOGUE_COMMONS.md):
  core         docs/catalogue/catalogue.json (the shared commons, 16 patterns)
  domain       optional pack files (--domain-pack), same entry shape
  org overlay  optional private file (--org-overlay), same entry shape,
               every entry forced private=True

Composition rules:
  - Every composed entry is annotated with source_layer in
    {"core", "domain", "org"} and a private flag (org -> True, else False).
  - Duplicate ids across domain packs are rejected (fail closed).
  - An org id may intentionally OVERRIDE a core/domain id: the org's private
    version wins and the override is recorded in the composition report.
  - Contribution files are validated by validate_contrib(), the executable
    enforcement of catalogue-contrib/contrib.v1.schema.json (the repo is
    stdlib-only, so the loader carries the schema's rules in code; the JSON
    Schema document is the normative contract and each check below cites the
    schema property it enforces).

Privacy property (unit-tested): strip_private() removes every private entry;
the check runner's --public-only mode re-seals bundles over public findings
only, so org entries appear in NO emitted public artifact — not even via
hashes.

Stdlib only. Usage:
  python3 tools/catalogue_loader.py --validate-contrib <file.json>
  python3 tools/catalogue_loader.py --compose [--domain-pack F ...]
      [--org-overlay F]   (prints the composition report as JSON)
"""

import json
import re
import sys
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORE_CATALOGUE = REPO / "docs" / "catalogue" / "catalogue.json"
CONTRIB_SCHEMA = REPO / "catalogue-contrib" / "contrib.v1.schema.json"

ID_RE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)+$")
SLOT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SLOT_REF_RE = re.compile(r"<([a-z][a-z0-9_]*)>")
DECISIONS = ("forbidden", "prompt", "allow", "unknown")
PROBE_EXPECTED = DECISIONS + ("unmatched-reported-as-unknown",)
DIRECTIONS = ("restrictive", "permissive", "guard")
PROVENANCE_KINDS = ("measured", "literature", "mined", "hypothesis")

SOURCE_LAYERS = ("core", "domain", "org")


class ContribViolation(ValueError):
    """A contribution file fails the contrib.v1 review bar."""


def _err(errors, msg):
    errors.append(msg)


def validate_contrib(entry):
    """Enforce catalogue-contrib/contrib.v1.schema.json. Returns [errors].

    Each check cites the schema property it enforces. Empty list = valid.
    """
    errors = []
    if not isinstance(entry, dict):
        return ["entry must be a JSON object"]

    # --- id (schema: id.pattern; lane rule in CONTRIBUTING.md) ---
    eid = entry.get("id")
    if not isinstance(eid, str) or not ID_RE.match(eid):
        _err(errors, "id: must match ^[A-Z0-9]+(-[A-Z0-9]+)+$")
    else:
        kind = entry.get("contribution_kind")
        if kind == "community" and not eid.startswith("FP-"):
            _err(errors, "id: community entries must start with 'FP-'")
        if kind == "org-overlay" and not eid.startswith("ORG-"):
            _err(errors, "id: org-overlay entries must start with 'ORG-'")

    # --- name (schema: name.pattern) ---
    name = entry.get("name")
    if not isinstance(name, str) or not re.match(r"^[a-z][a-z0-9_]*$", name):
        _err(errors, "name: snake_case, e.g. destructive_filesystem_delete")

    # --- intent (schema: intent.minLength 20) ---
    intent = entry.get("intent")
    if not isinstance(intent, str) or len(intent) < 20:
        _err(errors, "intent: plain-English protective intent, >= 20 chars")

    # --- intent_direction (schema enum) ---
    if entry.get("intent_direction") not in DIRECTIONS:
        _err(errors, f"intent_direction: must be one of {DIRECTIONS}")

    # --- parameters (schema: minItems 1; slot pattern) ---
    params = entry.get("parameters")
    slots = {}
    if not isinstance(params, list) or not params:
        _err(errors, "parameters: non-empty array (review bar: slots declared)")
    else:
        for i, p in enumerate(params):
            if not isinstance(p, dict):
                _err(errors, f"parameters[{i}]: must be an object")
                continue
            slot = p.get("slot")
            if not isinstance(slot, str) or not SLOT_RE.match(slot):
                _err(errors, f"parameters[{i}].slot: ^[a-z][a-z0-9_]*$")
            elif slot in slots:
                _err(errors, f"parameters[{i}].slot: duplicate slot {slot!r}")
            else:
                slots[slot] = p
            if not isinstance(p.get("description"), str) or not p["description"]:
                _err(errors, f"parameters[{i}].description: required")

    # --- expected_decision (schema enum, minItems 1) ---
    exp = entry.get("expected_decision")
    if (not isinstance(exp, list) or not exp
            or any(d not in DECISIONS for d in exp)):
        _err(errors, f"expected_decision: non-empty list of {DECISIONS}")

    # --- probe_families (schema: minItems 1; REVIEW BAR: no entry w/o probes) --
    fams = entry.get("probe_families")
    if not isinstance(fams, list) or not fams:
        _err(errors, "probe_families: at least one family "
                      "(review bar: an invariant without probes is a wish)")
    else:
        for i, pf in enumerate(fams):
            tag = f"probe_families[{i}]"
            if not isinstance(pf, dict):
                _err(errors, f"{tag}: must be an object")
                continue
            if not pf.get("family"):
                _err(errors, f"{tag}.family: required")
            probes = pf.get("probes")
            if not isinstance(probes, list) or not probes:
                _err(errors, f"{tag}.probes: at least one probe")
            else:
                for j, probe in enumerate(probes):
                    if (not isinstance(probe, list) or not probe
                            or any(not isinstance(t, str) or not t
                                   for t in probe)):
                        _err(errors, f"{tag}.probes[{j}]: non-empty argv "
                                      "template (list of strings)")
                        continue
                    for tok in probe:
                        for ref in SLOT_REF_RE.findall(tok):
                            if ref not in slots:
                                _err(errors,
                                       f"{tag}.probes[{j}]: <{ref}> is not a "
                                       "declared parameter slot")
            pexp = pf.get("expected")
            if (not isinstance(pexp, list) or not pexp
                    or any(d not in PROBE_EXPECTED for d in pexp)):
                _err(errors, f"{tag}.expected: non-empty list of "
                              f"{PROBE_EXPECTED}")

    # --- provenance (schema: required kind+detail) ---
    prov = entry.get("provenance")
    if not isinstance(prov, dict):
        _err(errors, "provenance: required (review bar: no anonymous "
                      "invariants)")
    else:
        if prov.get("kind") not in PROVENANCE_KINDS:
            _err(errors, f"provenance.kind: one of {PROVENANCE_KINDS}")
        detail = prov.get("detail")
        if not isinstance(detail, str) or len(detail) < 10:
            _err(errors, "provenance.detail: >= 10 chars "
                          "(doc URL + date, paper, incident, or reasoning)")
        if prov.get("kind") == "measured" and not prov.get("measured_on"):
            _err(errors, "provenance.measured_on: required when kind=measured")

    # --- author / licence (schema: required) ---
    author = entry.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        _err(errors, "author.name: required")
    if not entry.get("licence"):
        _err(errors, "licence: required (e.g. CC-BY-4.0, or 'org-private — "
                      "not for redistribution')")

    # --- contribution_kind + private (schema allOf lanes) ---
    kind = entry.get("contribution_kind")
    if kind not in ("community", "org-overlay"):
        _err(errors, "contribution_kind: 'community' or 'org-overlay'")
    private = entry.get("private", False)
    if kind == "org-overlay" and private is not True:
        _err(errors, "private: org-overlay entries MUST be true "
                      "(privacy property)")
    if kind == "community" and private is True:
        _err(errors, "private: community entries must not be private")

    # --- measurement_status (schema enum; measured-before-claimed rule) ---
    ms = entry.get("measurement_status", "UNMEASURED")
    if ms not in ("MEASURED", "UNMEASURED"):
        _err(errors, "measurement_status: MEASURED or UNMEASURED")
    if ms == "MEASURED":
        if not isinstance(prov, dict) or prov.get("kind") != "measured":
            _err(errors, "measurement_status MEASURED requires "
                          "provenance.kind=measured (measured-before-claimed)")
        elif not prov.get("measured_on"):
            _err(errors, "measurement_status MEASURED requires "
                          "provenance.measured_on naming harness+version")
        if not entry.get("evidence_refs"):
            _err(errors, "measurement_status MEASURED requires evidence_refs")

    return errors


def load_core(path=None):
    """Load the core catalogue entries."""
    doc = json.loads(Path(path or CORE_CATALOGUE).read_text())
    return doc["entries"], {"catalogue_version": doc.get("catalogue_version"),
                            "path": str(Path(path or CORE_CATALOGUE))}


def load_pack_file(path):
    """Load a domain-pack or overlay file.

    Accepts {"entries": [...]}, a bare JSON array, or a single entry object
    (treated as a one-entry pack). Overlay files may also carry
    {"private": true} at top level; entries are still forced private at
    composition time.
    """
    doc = json.loads(Path(path).read_text())
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        if isinstance(doc.get("entries"), list):
            return doc["entries"]
        if doc.get("id"):
            return [doc]
    raise ContribViolation(f"{path}: expected a JSON entry object, array, or "
                           '{"entries": [...]}')


def compose(core_entries, domain_packs=None, org_overlay=None):
    """Compose the three layers into one annotated entry list.

    domain_packs: list of (label, entries). org_overlay: (label, entries).
    Returns (entries, report). Each entry gains source_layer + private.
    Raises ContribViolation on duplicate ids outside the org-override rule.
    """
    entries = []
    seen = {}
    report = {"core": 0, "domain": {}, "org": {"entries": 0, "private": True},
              "overrides": [], "duplicates_rejected": []}

    def add(entry, layer, label):
        eid = entry.get("id")
        if not eid:
            raise ContribViolation(f"{label}: entry without id")
        e = deepcopy(entry)
        e["source_layer"] = layer
        e["private"] = (layer == "org")
        if eid in seen:
            prev_layer, prev_label = seen[eid]
            if layer == "org":
                # Org override: private version wins; drop the earlier one.
                entries[:] = [x for x in entries if x["id"] != eid]
                report["overrides"].append(
                    {"id": eid, "overridden_layer": prev_layer,
                     "overridden_from": prev_label})
            else:
                report["duplicates_rejected"].append(
                    {"id": eid, "layer": layer, "label": label,
                     "first_seen": prev_label})
                raise ContribViolation(
                    f"duplicate id {eid!r} in {label} "
                    f"(first seen in {prev_label}); refusing to compose")
        seen[eid] = (layer, label)
        entries.append(e)
        return e

    for e in core_entries:
        add(e, "core", "core")
    report["core"] = sum(1 for e in entries if e["source_layer"] == "core")
    for label, pack_entries in (domain_packs or []):
        n0 = len(entries)
        for e in pack_entries:
            add(e, "domain", label)
        report["domain"][label] = len(entries) - n0
    if org_overlay:
        label, overlay_entries = org_overlay
        n0 = len(entries)
        for e in overlay_entries:
            add(e, "org", label)
        report["org"]["entries"] = len(entries) - n0
    report["total"] = len(entries)
    return entries, report


def strip_private(entries):
    """Return only the non-private entries (the public artifact view)."""
    return [e for e in entries if not e.get("private")]


def public_text_contains_private(entries, text):
    """Privacy check helper: does emitted text name any private entry id?"""
    private_ids = [e["id"] for e in entries if e.get("private")]
    hits = [i for i in private_ids if i in text]
    return hits


def _validate_file(path):
    entry = json.loads(Path(path).read_text())
    # Accept a single entry object or {"entries": [...]} (validate each).
    targets = entry["entries"] if isinstance(entry, dict) and isinstance(
        entry.get("entries"), list) else [entry]
    ok = True
    for t in targets:
        errors = validate_contrib(t)
        label = t.get("id", "?") if isinstance(t, dict) else "?"
        if errors:
            ok = False
            print(f"{path} [{label}]: INVALID")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"{path} [{label}]: valid")
    return ok


def main(argv):
    if "--validate-contrib" in argv:
        idx = argv.index("--validate-contrib")
        paths = []
        for a in argv[idx + 1:]:
            if a.startswith("--"):
                break
            paths.append(a)
        if not paths:
            sys.exit("usage: catalogue_loader.py --validate-contrib <file> [...]")
        ok = all(_validate_file(p) for p in paths)
        return 0 if ok else 1
    if "--compose" in argv:
        domain_packs = []
        org_overlay = None
        args = argv[argv.index("--compose") + 1:]
        i = 0
        while i < len(args):
            if args[i] == "--domain-pack":
                p = args[i + 1]
                domain_packs.append((p, load_pack_file(p)))
                i += 2
            elif args[i] == "--org-overlay":
                p = args[i + 1]
                org_overlay = (p, load_pack_file(p))
                i += 2
            else:
                sys.exit(f"unknown --compose flag: {args[i]}")
        core_entries, _ = load_core()
        entries, report = compose(core_entries, domain_packs, org_overlay)
        print(json.dumps(report, indent=2))
        return 0
    sys.exit("usage: catalogue_loader.py (--validate-contrib F... | --compose "
             "[--domain-pack F] [--org-overlay F])")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
