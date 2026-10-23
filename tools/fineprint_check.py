#!/usr/bin/env python3
"""FinePrint conformance-check runner (Catalogue Commons product wedge).

A single command that takes an invariant pack (core catalogue + optional
domain packs + optional org-private overlay), a harness adapter, and a
policy config; runs the pack's probes; and emits:

  bundle.json      sealed check-run evidence bundle (check-run-bundle.v1:
                   per-probe findings, per-invariant dual verdicts,
                   Merkle-sealed, claim scope = MEASURED entries only)
  scorecard.json   machine-readable scorecard (fineprint-check-scorecard.v1)
  scorecard.html   standalone readable scorecard
  bindings.json    the parameter bindings the run used
  composition.json the pack composition report

Deployment-gate mode (--baseline <bundle.json>): diffs the fresh run
against a previous sealed bundle and reports REGRESSIONS — an invariant
that was satisfied and is now unresolved/not-satisfied, a decision flip,
or a dropped invariant.

Exit codes: 0 = run ok, no regressions; 1 = usage/runtime error;
            2 = regressions found (--baseline mode).

Usage:
  python3 tools/fineprint_check.py --harness codex \\
      --policy fixtures/policies/default.rules \\
      [--domain-pack FILE ...] [--org-overlay FILE] \\
      [--bindings FILE] [--only FP-001,FP-002] \\
      [--out DIR] [--label NAME] [--public-only] [--sign] \\
      [--baseline <bundle.json>]
  python3 tools/fineprint_check.py --list-adapters

Parameter bindings: JSON {"FP-001": {"command_bin": "rm", ...}}. Any slot
without an explicit binding falls back to the catalogue entry's example
value; a required slot with neither fails closed. The demo runs use the
examples as sample bindings (recorded in bindings.json).

Privacy: org-overlay entries are flagged private:true in default output
(this machine only). --public-only strips them BEFORE sealing — the bundle
is re-sealed over public findings only, so no private content leaks
through the Merkle tree either.

Stdlib only.
"""

import json
import re
import shlex
import sys
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import catalogue_loader as CL  # noqa: E402
import check_adapters as AD  # noqa: E402
import check_bundle as CB  # noqa: E402
import check_scorecard as CS  # noqa: E402
import schemas_v1 as S  # noqa: E402

SLOT_REF_RE = re.compile(r"<([a-z][a-z0-9_]*)>")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REGRESSIONS = 2


def parse_args(argv):
    a = {"domain_pack": [], "org_overlay": None, "bindings": None,
         "only": None, "out": None, "label": "check", "baseline": None,
         "public_only": False, "sign": False, "list_adapters": False,
         "harness": None, "policy": None}
    i = 0
    while i < len(argv):
        t = argv[i]
        if t == "--harness":
            a["harness"] = argv[i + 1]; i += 2
        elif t == "--policy":
            a["policy"] = argv[i + 1]; i += 2
        elif t == "--domain-pack":
            a["domain_pack"].append(argv[i + 1]); i += 2
        elif t == "--org-overlay":
            a["org_overlay"] = argv[i + 1]; i += 2
        elif t == "--bindings":
            a["bindings"] = argv[i + 1]; i += 2
        elif t == "--only":
            a["only"] = [x.strip() for x in argv[i + 1].split(",") if x.strip()]
            i += 2
        elif t == "--out":
            a["out"] = argv[i + 1]; i += 2
        elif t == "--label":
            a["label"] = argv[i + 1]; i += 2
        elif t == "--baseline":
            a["baseline"] = argv[i + 1]; i += 2
        elif t == "--public-only":
            a["public_only"] = True; i += 1
        elif t == "--sign":
            a["sign"] = True; i += 1
        elif t == "--list-adapters":
            a["list_adapters"] = True; i += 1
        elif t in ("-h", "--help"):
            print(__doc__); sys.exit(0)
        else:
            sys.exit(f"unknown flag: {t}\n{__doc__}")
    return a


def probe_slot_refs(entries):
    """All <slot> names referenced by probe templates, per invariant id."""
    refs = {}
    for e in entries:
        seen = set()
        for pf in e.get("probe_families", []):
            for template in pf["probes"]:
                for tok in template:
                    seen.update(SLOT_REF_RE.findall(tok))
        refs[e["id"]] = seen
    return refs


def load_bindings(path, entries):
    """Per-invariant slot bindings; default = catalogue examples.

    The core catalogue's probe templates reference a few slots that are not
    in the entries' declared parameter lists (known catalogue data gap, see
    docs/CATALOGUE_COMMONS.md). Those slots can ONLY be bound explicitly via
    --bindings (per-id or __default__); they are never invented. Every such
    binding is recorded in the returned undeclared map and in the run's
    composition.json. A slot with no binding anywhere fails closed.
    """
    explicit = {}
    if path:
        explicit = json.loads(Path(path).read_text())
        if not isinstance(explicit, dict):
            sys.exit("--bindings must be a JSON object")
    refs = probe_slot_refs(entries)
    resolved, undeclared = {}, {}
    for e in entries:
        eid = e["id"]
        b = {}
        declared = {p["slot"] for p in e.get("parameters", [])}
        for p in e.get("parameters", []):
            slot = p["slot"]
            val = (explicit.get(eid, {}) or {}).get(slot)
            if val is None:
                val = (explicit.get("__default__", {}) or {}).get(slot)
            if val is None:
                val = p.get("example")
            if val is None and p.get("required", True):
                sys.exit(f"{eid}: no binding for required slot <{slot}> "
                         "(no --bindings value and no example)")
            if val is not None:
                b[slot] = val
        for slot in sorted(refs[eid] - declared):
            val = (explicit.get(eid, {}) or {}).get(slot)
            if val is None:
                val = (explicit.get("__default__", {}) or {}).get(slot)
            if val is None:
                sys.exit(f"{eid}: probe references <{slot}>, which is not "
                         "a declared parameter and has no --bindings value "
                         "(refusing to invent a binding)")
            b[slot] = val
            undeclared.setdefault(eid, {})[slot] = val
        resolved[eid] = b
    return resolved, undeclared


def substitute(argv_template, bindings, entry_id, probe_id):
    """Bind <slot> placeholders. Binding values may be strings or lists of
    strings (lists are spliced into argv, e.g. deny_args: ["-rf", "/tmp/x"])."""
    out = []
    for tok in argv_template:
        refs = SLOT_REF_RE.findall(tok)
        if not refs:
            out.append(tok)
            continue
        if len(refs) == 1 and SLOT_REF_RE.fullmatch(tok):
            slot = refs[0]
            if slot not in bindings:
                sys.exit(f"{probe_id}: <{slot}> has no binding "
                         f"(invariant {entry_id})")
            val = bindings[slot]
            out.extend(val if isinstance(val, list) else [str(val)])
        else:
            def rep(m):
                slot = m.group(1)
                if slot not in bindings:
                    sys.exit(f"{probe_id}: <{slot}> has no binding "
                             f"(invariant {entry_id})")
                val = bindings[slot]
                if isinstance(val, list):
                    sys.exit(f"{probe_id}: list binding <{slot}> cannot be "
                             "embedded inside a larger token")
                return str(val)
            out.append(SLOT_REF_RE.sub(rep, tok))
    return out


def normalize_expected(raw):
    if raw == "unmatched-reported-as-unknown":
        return "unknown"
    return raw


def family_expectations(pf):
    """Resolve a probe family's expected list to per-probe expectation SETS.

    Two encodings exist in the catalogue:
      positional: len(expected) == len(probes) > 1 (FP-012 direct:
                  [allow, forbidden] maps probe-by-probe);
      alternatives: anything else — the probe passes when its actual decision
                  is any member of the normalized set (FP-002 direct:
                  [prompt, forbidden] with one probe).
    Returns a list of sets, one per probe. Anything ambiguous fails closed.
    """
    n_probes = len(pf["probes"])
    raw = pf["expected"]
    normed = [normalize_expected(x) for x in raw]
    if n_probes > 1 and len(raw) == n_probes:
        return [{x} for x in normed]
    return [set(normed) for _ in pf["probes"]]


def expand_probes(entries, bindings):
    """Yield (entry, probe_id, family, argv, expected, bindings) per probe.

    probe_id = "<id>/<family>/p<n>" with n a per-entry running index (unique
    even when an entry repeats a family name, e.g. FP-011's two "variant"
    families). Stable for a fixed pack; the pack hash is pinned in the
    bundle, so baseline diffs compare like with like.
    """
    for e in entries:
        eid = e["id"]
        b = bindings[eid]
        n = 0
        for pf in e.get("probe_families", []):
            family = pf["family"]
            exp_sets = family_expectations(pf)
            for template, exp_set in zip(pf["probes"], exp_sets):
                probe_id = f"{eid}/{family}/p{n}"
                argv = substitute(template, b, eid, probe_id)
                yield e, probe_id, family, argv, exp_set, b
                n += 1


def run_pack(entries, bindings, adapter, policy):
    findings = []
    for e, probe_id, family, argv, exp_set, b in expand_probes(
            entries, bindings):
        res = adapter["run_probe"](argv, policy)
        actual = res["actual"]
        if actual == "error":
            verdict = "not_run"
        else:
            verdict = "pass" if actual in exp_set else "fail"
        expected_primary = sorted(exp_set)[0]
        findings.append({
            "probe_id": probe_id,
            "invariant_id": e["id"],
            "probe_family": family,
            "argv": argv,
            "parameter_bindings": dict(b),
            "expected_decision": expected_primary,
            "expected_decisions": sorted(exp_set),
            "actual_decision": actual,
            "verdict": verdict,
            "layer": res["layer"],
            "layer_attribution": (res["note"] if actual == "unknown"
                                  else ""),
            "evidence_class": adapter["evidence_class"],
            "matched_rules": res["matched_rules"],
            "engine_note": res["note"],
            "raw_native_output": res["raw"],
            "source_layer": e.get("source_layer", "core"),
            "private": bool(e.get("private")),
            "expectation_basis": e.get("expectation_basis", ""),
        })
    return findings


def build_run_spec(args, adapter_name, adapter, policy_path, entries,
                   report, bindings):
    policy_p = Path(policy_path)
    if not policy_p.exists():
        sys.exit(f"--policy not found: {policy_path}")
    core_doc = json.loads(CL.CORE_CATALOGUE.read_text())
    pack_canonical = S.canonical_json(
        [{"id": e["id"], "source_layer": e.get("source_layer"),
          "private": bool(e.get("private"))} for e in entries])
    return {
        "harness": adapter_name,
        "adapter_tier": adapter["tier"],
        "adapter_version_detail": adapter.get("version_detail", ""),
        "evidence_class": adapter["evidence_class"],
        "policy": {"path": str(policy_p),
                   "sha256": S.sha256_file(str(policy_p)),
                   "kind": adapter["policy_kind"]},
        "pack": {
            "core": {"path": "docs/catalogue/catalogue.json",
                     "sha256": S.sha256_file(str(CL.CORE_CATALOGUE)),
                     "catalogue_version": core_doc.get("catalogue_version", ""),
                     "entries": report["core"]},
            "domain_packs": [{"label": k, "entries": v}
                             for k, v in report["domain"].items()],
            "org_overlay": {"present": report["org"]["entries"] > 0,
                            "entries": report["org"]["entries"]},
            "composition_sha256": S.sha256_hex(pack_canonical.encode()),
            "total_entries": len(entries),
        },
        "parameter_bindings_sha256": S.sha256_hex(
            S.canonical_json(bindings).encode()),
        "probe_count": None,  # filled by caller
    }


def claim_scope(invariant_results):
    measured = [r for r in invariant_results
                if r.get("measurement_status") == "MEASURED"]
    return {
        "note": ("Measured-before-claimed: the conformance claim covers "
                 "MEASURED entries only. UNMEASURED entries are exploratory: "
                 "probes ran, but no conformance claim is made."),
        "measured_invariants": len(measured),
        "measured_satisfied": sum(1 for r in measured
                                  if r["intent_coverage"] == "SATISFIED"),
        "measured_unresolved": sum(1 for r in measured
                                   if r["intent_coverage"] == "UNRESOLVED"),
        "measured_not_satisfied": sum(
            1 for r in measured if r["intent_coverage"] == "NOT_SATISFIED"),
        "exploratory_invariants": len(invariant_results) - len(measured),
    }


def diff_bundles(baseline, fresh):
    """Diff fresh vs baseline sealed bundles. Returns a report dict."""
    base = {r["invariant_id"]: r
            for r in baseline["invariant_results"]}
    new = {r["invariant_id"]: r for r in fresh["invariant_results"]}
    base_probes = {f["probe_id"]: f for f in baseline["findings"]}
    new_probes = {f["probe_id"]: f for f in fresh["findings"]}

    regressions, improvements, flips, added, dropped = [], [], [], [], []

    def is_reg(b_cov, f_cov):
        br, fr = CS.COVERAGE_RANK[b_cov], CS.COVERAGE_RANK[f_cov]
        return fr < br

    for iid, b in base.items():
        f = new.get(iid)
        if f is None:
            dropped.append(iid)
            regressions.append({"kind": "dropped-invariant",
                                "invariant_id": iid,
                                "detail": "present in baseline, absent in "
                                          "fresh run"})
            continue
        b_cov, f_cov = b["intent_coverage"], f["intent_coverage"]
        if b_cov != "NOT_APPLICABLE" and f_cov != "NOT_APPLICABLE":
            if is_reg(b_cov, f_cov):
                regressions.append({
                    "kind": "coverage-regression", "invariant_id": iid,
                    "baseline": b_cov, "fresh": f_cov,
                    "detail": f"intent coverage {b_cov} -> {f_cov}"})
            elif CS.COVERAGE_RANK[f_cov] > CS.COVERAGE_RANK[b_cov]:
                improvements.append({"invariant_id": iid, "baseline": b_cov,
                                     "fresh": f_cov})
        for pid, fp in ((p["probe_id"], p) for p in f["probe_rows"]):
            bp = base_probes.get(pid)
            if bp and bp["actual_decision"] != fp["actual_decision"]:
                flip = {"kind": "decision-flip", "probe_id": pid,
                        "invariant_id": iid,
                        "baseline_actual": bp["actual_decision"],
                        "fresh_actual": fp["actual_decision"]}
                flips.append(flip)
                # A protective decision lost on a restrictive invariant is a
                # regression even when the aggregate rank did not move
                # (e.g. UNRESOLVED stayed UNRESOLVED but gained an allow).
                if (f.get("intent_direction") == "restrictive"
                        and bp["actual_decision"] in ("forbidden", "prompt")
                        and fp["actual_decision"] in ("allow", "unknown")):
                    regressions.append({**flip,
                                        "kind": "decision-flip-regression"})
    for iid in new:
        if iid not in base:
            added.append(iid)

    return {"baseline_bundle": baseline["bundle_id"],
            "fresh_bundle": fresh["bundle_id"],
            "regressions": regressions, "improvements": improvements,
            "decision_flips": flips, "added_invariants": added,
            "dropped_invariants": dropped,
            "regression_count": len(regressions)}


def gate_exit_code(diff):
    """Deployment-gate exit contract: 0 = no regressions, 2 = regressions."""
    return EXIT_REGRESSIONS if diff["regression_count"] else EXIT_OK


def main(argv):
    args = parse_args(argv)
    if args["list_adapters"]:
        print(json.dumps(AD.list_adapters(), indent=2))
        return EXIT_OK
    if not args["harness"] or not args["policy"]:
        sys.exit("--harness and --policy are required\n" + __doc__)
    if args["harness"] not in AD.ADAPTERS:
        sys.exit(f"unknown harness {args['harness']!r}; "
                 f"see --list-adapters")

    adapter = AD.ADAPTERS[args["harness"]]
    ok, detail = adapter["check_environment"]()
    if not ok:
        sys.exit(f"adapter {args['harness']} not runnable: {detail}\n"
                 "Refusing to fabricate probe results.")
    print(f"adapter: {args['harness']} ({adapter['tier']}) — {detail}")

    # --- compose the pack ---
    core_entries, _ = CL.load_core()
    domain_packs = [(p, CL.load_pack_file(p)) for p in args["domain_pack"]]
    org = None
    if args["org_overlay"]:
        org = (args["org_overlay"], CL.load_pack_file(args["org_overlay"]))
    entries, report = CL.compose(core_entries, domain_packs, org)
    if args["only"]:
        want = set(args["only"])
        entries = [e for e in entries if e["id"] in want]
        missing = want - {e["id"] for e in entries}
        if missing:
            sys.exit(f"--only names unknown ids: {sorted(missing)}")
    print(f"pack: {len(entries)} invariants "
          f"(core={report['core']}, "
          f"domain={sum(report['domain'].values())}, "
          f"org={report['org']['entries']}"
          f"{' PRIVATE' if report['org']['entries'] else ''})")

    bindings, undeclared = load_bindings(args["bindings"], entries)

    out_dir = Path(args["out"]) if args["out"] else None

    # --- run the probes ---
    findings = run_pack(entries, bindings, adapter, args["policy"])
    by_inv = {}
    for f in findings:
        by_inv.setdefault(f["invariant_id"], []).append(f)
    entry_by_id = {e["id"]: e for e in entries}
    has_source = adapter["has_decision_source"]
    invariant_results = [CS.adjudicate(entry_by_id[iid], by_inv[iid],
                                      has_source)
                         for iid in [e["id"] for e in entries]]

    # --- privacy: strip private entries BEFORE sealing in public mode ---
    public_mode = args["public_only"]
    if public_mode:
        pub_ids = {e["id"] for e in entries if not e.get("private")}
        findings = [f for f in findings if f["invariant_id"] in pub_ids]
        invariant_results = [r for r in invariant_results
                             if r["invariant_id"] in pub_ids]
    privacy = {"public_mode": public_mode,
               "org_entries_included": (not public_mode
                                        and report["org"]["entries"] > 0),
               "org_entries": report["org"]["entries"]}

    run_spec = build_run_spec(args, args["harness"], adapter,
                              args["policy"], entries, report, bindings)
    run_spec["adapter_version_detail"] = detail
    run_spec["probe_count"] = len(findings)

    bundle = CB.seal_check_bundle(
        label=args["label"], run_spec=run_spec, findings=findings,
        invariant_results=invariant_results,
        claim_scope=claim_scope(invariant_results), privacy=privacy,
        sign=args["sign"],
        out_path=str(out_dir / "bundle.json") if out_dir and args["sign"]
        else None)

    verify_problems = CB.verify_check_bundle(bundle)
    if verify_problems:
        print("BUNDLE SELF-VERIFY FAILED:")
        for p in verify_problems:
            print(f"  - {p}")
        return EXIT_ERROR

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = out_dir / "bundle.json"
        if not args["sign"]:
            bundle_path.write_text(json.dumps(bundle, indent=2) + "\n")
        if public_mode:
            pub_ids = {e["id"] for e in entries if not e.get("private")}
            pub_bindings = {k: v for k, v in bindings.items()
                            if k in pub_ids}
        else:
            pub_bindings = bindings
        (out_dir / "bindings.json").write_text(
            json.dumps(pub_bindings, indent=2) + "\n")
        composition = dict(report)
        composition["undeclared_slot_bindings"] = undeclared
        composition["undeclared_slot_note"] = (
            "Probe templates referencing slots outside the entries' declared "
            "parameter lists (known core-catalogue data gap). These slots "
            "were bound EXPLICITLY via --bindings (never invented); the "
            "values above are the ones the probes ran with.")
        (out_dir / "composition.json").write_text(
            json.dumps(composition, indent=2) + "\n")
        cmd_argv = ["tools/fineprint_check.py"] + sys.argv[1:]
        repro_suffix = ""
        if public_mode:
            # Reconstruct the public recipe from effective parameters: the
            # overlay path and any private ids in --only must never appear
            # in a public artifact (both can name the org). The sanitized
            # recipe reproduces the sealed PUBLIC bundle as-is.
            pub_ids = {e["id"] for e in entries if not e.get("private")}
            parts = ["tools/fineprint_check.py",
                     "--harness", args["harness"],
                     "--policy", args["policy"]]
            for p in args["domain_pack"]:
                parts += ["--domain-pack", p]
            if args["bindings"]:
                parts += ["--bindings", args["bindings"]]
            if args["only"] is not None:
                only_pub = [i for i in args["only"] if i in pub_ids]
                parts += ["--only", ",".join(only_pub)]
            if args["baseline"]:
                parts += ["--baseline", args["baseline"]]
            if args["out"]:
                parts += ["--out", args["out"]]
            if args["label"] != "check":
                parts += ["--label", args["label"]]
            parts += ["--public-only"]
            if args["sign"]:
                parts += ["--sign"]
            cmd_argv = parts
            repro_suffix = (" Public view: the org overlay is omitted from "
                            "this recipe; re-running it reproduces the "
                            "sealed public bundle as-is.")
        repro = "python3 " + " ".join(shlex.quote(x) for x in cmd_argv)
        CS.build_scorecard(bundle, out_dir, repro,
                           repro_note_suffix=repro_suffix)
        print(f"wrote {out_dir}/bundle.json (+ scorecard.json/html, "
              f"bindings.json, composition.json)")
    else:
        print(json.dumps({"bundle_id": bundle["bundle_id"],
                          "status": bundle["status"],
                          "verdicts": bundle["verdicts"],
                          "dual_verdict_summary":
                              bundle["dual_verdict_summary"]}, indent=2))

    v = bundle["verdicts"]
    d = bundle["dual_verdict_summary"]
    print(f"bundle {bundle['bundle_id']}: status={bundle['status']} "
          f"pass={v['pass']} fail={v['fail']} not_run={v['not_run']}")
    print(f"intent: SATISFIED={d['intent_coverage']['SATISFIED']} "
          f"NOT_SATISFIED={d['intent_coverage']['NOT_SATISFIED']} "
          f"UNRESOLVED={d['intent_coverage']['UNRESOLVED']} "
          f"NOT_APPLICABLE={d['intent_coverage']['NOT_APPLICABLE']}")

    # --- deployment-gate mode ---
    if args["baseline"]:
        baseline = json.loads(Path(args["baseline"]).read_text())
        if baseline.get("schema_version") != "check-run-bundle.v1":
            sys.exit("--baseline must be a check-run-bundle.v1 bundle")
        diff = diff_bundles(baseline, bundle)
        if out_dir:
            (out_dir / "baseline-diff.json").write_text(
                json.dumps(diff, indent=2) + "\n")
        print(f"\nbaseline {diff['baseline_bundle'][:24]}… vs "
              f"fresh {diff['fresh_bundle'][:24]}…")
        for r in diff["regressions"]:
            print(f"  REGRESSION [{r['kind']}] "
                  f"{r.get('invariant_id') or r.get('probe_id')}: "
                  f"{r.get('detail') or (r.get('baseline_actual') + ' -> ' + r.get('fresh_actual'))}")
        for fl in diff["decision_flips"]:
            if fl["kind"] == "decision-flip":
                print(f"  flip {fl['probe_id']}: {fl['baseline_actual']} -> "
                      f"{fl['fresh_actual']}")
        for i in diff["improvements"]:
            print(f"  improvement {i['invariant_id']}: {i['baseline']} -> "
                  f"{i['fresh']}")
        if diff["added_invariants"]:
            print(f"  added: {diff['added_invariants']}")
        if diff["dropped_invariants"]:
            print(f"  dropped: {diff['dropped_invariants']}")
        print(f"regressions: {diff['regression_count']}")
        if diff["regression_count"]:
            print("GATE: BLOCKED (nonzero exit)")
        else:
            print("GATE: PASS (no regressions)")
        return gate_exit_code(diff)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
