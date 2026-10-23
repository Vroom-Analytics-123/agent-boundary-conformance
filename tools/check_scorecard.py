#!/usr/bin/env python3
"""Adjudicate + render FinePrint check-run scorecards.

Reads a SEALED check-run bundle (committed input only — no oracle calls,
fully deterministic except the generated_utc timestamp; a third party with
the repo and the bundle re-issues the scorecard with the command in the
reproducibility footer) and emits:

  scorecard.json  machine-readable (schema "fineprint-check-scorecard.v1"):
                  per-invariant dual-verdict rows with per-probe detail
  scorecard.html  standalone readable report (inline CSS, no external assets)

Dual-verdict aggregation (per invariant), from tools/dual_verdict.py's
discipline — the two judgments are orthogonal and never conflated:

  measurement_validity: PASS (every probe executed and matched expectation)
                        / FAIL (a probe's actual differed from expected)
                        / NOT_REPRODUCED (a probe did not run)
  intent_coverage:      SATISFIED / NOT_SATISFIED / UNRESOLVED / NOT_APPLICABLE
      restrictive: NOT_SATISFIED if any probe actual is allow;
                   UNRESOLVED if any actual is unknown or a probe errored
                   (the rules layer did not establish the protection);
                   SATISFIED only when every probe actual is forbidden/prompt.
      permissive:  SATISFIED iff every probe actual is allow.
      guard:       NOT_APPLICABLE (methodological self-checks, not
                   protection claims).
  A correctly reported unknown is measurement PASS (when expected) but
  intent UNRESOLVED — never a passed invariant.

Stdlib only. Used by tools/fineprint_check.py; also runnable standalone:
  python3 tools/check_scorecard.py --bundle <bundle.json> --out <dir>
"""

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import dual_verdict as DV  # noqa: E402

SEMANTICS = {
    "measurement_validity": ("PASS / FAIL / NOT_REPRODUCED — did every probe "
                             "execute on the harness and match the pack's "
                             "expectation?"),
    "intent_coverage": ("SATISFIED / NOT_SATISFIED / UNRESOLVED / "
                        "NOT_APPLICABLE — does the measured layer establish "
                        "the owner's stated protection? UNRESOLVED whenever "
                        "the layer cannot establish it; a correctly reported "
                        "unknown is never a satisfied invariant."),
    "observed_effect": ("NOT_TESTED for all check-run probes: no command is "
                        "ever executed; the harness is only asked for its "
                        "ruling."),
    "unknown_kinds": ("no-rule-match: the decision source returned no rule "
                      "decision; insufficient-runtime-evidence: n/a for "
                      "check runs (no runtime probes); unsupported-adapter: "
                      "no decision source for this harness."),
}

COVERAGE_RANK = {"SATISFIED": 3, "UNRESOLVED": 2, "NOT_SATISFIED": 1,
                 "NOT_APPLICABLE": 0}


def _probe_dual_verdict(entry, finding, has_source=True):
    """Dual verdict for one probe finding."""
    direction = entry.get("intent_direction", "guard")
    actual = finding["actual_decision"]
    verdict = finding["verdict"]

    if verdict == "not_run":
        mv = "NOT_REPRODUCED"
    elif verdict == "pass":
        mv = "PASS"
    else:
        mv = "FAIL"

    if direction == "guard":
        ic = "NOT_APPLICABLE"
    elif verdict == "not_run":
        ic = "UNRESOLVED"
    elif direction == "restrictive":
        exp_set = set(finding.get("expected_decisions")
                      or [finding["expected_decision"]])
        if actual == "allow" and "allow" not in exp_set:
            # An allow the pack did not sanction: the protection failed.
            ic = "NOT_SATISFIED"
        elif actual == "unknown":
            ic = "UNRESOLVED"
        else:
            ic = "SATISFIED"
    elif direction == "permissive":
        ic = "SATISFIED" if actual == "allow" else "NOT_SATISFIED"
    else:  # pragma: no cover - defensive
        ic = "NOT_APPLICABLE"

    shim = {"actual_decision": actual,
            "native_matched_rules_count": (
                finding.get("matched_rules")
                if isinstance(finding.get("matched_rules"), int)
                else (1 if finding.get("matched_rules") else 0))}
    uk = DV.unknown_kind_for(shim, has_oracle=has_source)
    return {"measurement_validity": mv, "intent_coverage": ic,
            "unknown_kind": uk}


def adjudicate(entry, probe_findings, has_source=True):
    """Aggregate per-probe findings to one invariant-level dual verdict."""
    direction = entry.get("intent_direction", "guard")
    per_probe = [_probe_dual_verdict(entry, f, has_source)
                 for f in probe_findings]

    mvs = [p["measurement_validity"] for p in per_probe]
    if "NOT_REPRODUCED" in mvs:
        mv = "NOT_REPRODUCED"
    elif "FAIL" in mvs:
        mv = "FAIL"
    else:
        mv = "PASS"

    if direction == "guard":
        ic = "NOT_APPLICABLE"
    elif mv == "NOT_REPRODUCED":
        ic = "UNRESOLVED"
    elif direction == "restrictive":
        unsanctioned_allow = any(
            f["actual_decision"] == "allow"
            and "allow" not in set(f.get("expected_decisions")
                                   or [f["expected_decision"]])
            for f in probe_findings)
        if unsanctioned_allow:
            ic = "NOT_SATISFIED"
        elif any(f["actual_decision"] in ("unknown", "error")
                 for f in probe_findings):
            ic = "UNRESOLVED"
        else:
            ic = "SATISFIED"
    elif direction == "permissive":
        actuals = [f["actual_decision"] for f in probe_findings]
        ic = "SATISFIED" if all(a == "allow" for a in actuals) \
            else "NOT_SATISFIED"
    else:  # pragma: no cover - defensive
        ic = "NOT_APPLICABLE"

    uk = {"no-rule-match": 0, "insufficient-runtime-evidence": 0,
          "unsupported-adapter": 0}
    for p in per_probe:
        if p["unknown_kind"]:
            uk[p["unknown_kind"]] += 1

    counts = {"pass": sum(1 for f in probe_findings
                          if f["verdict"] == "pass"),
              "fail": sum(1 for f in probe_findings
                          if f["verdict"] == "fail"),
              "not_run": sum(1 for f in probe_findings
                             if f["verdict"] == "not_run")}
    return {
        "invariant_id": entry["id"],
        "name": entry.get("name", ""),
        "family": entry.get("family", ""),
        "intent_direction": direction,
        "severity": entry.get("severity", ""),
        "source_layer": entry.get("source_layer", "core"),
        "private": bool(entry.get("private")),
        "expectation_basis": entry.get("expectation_basis", ""),
        "measurement_status": entry.get("measurement_status", ""),
        "measurement_validity": mv,
        "intent_coverage": ic,
        "unknown_kinds": uk,
        "probes": counts,
        "probe_ids": [f["probe_id"] for f in probe_findings],
        "probe_rows": [
            {"probe_id": f["probe_id"], "probe_family": f["probe_family"],
             "argv": f["argv"], "expected_decision": f["expected_decision"],
             "expected_decisions": f.get("expected_decisions",
                                         [f["expected_decision"]]),
             "actual_decision": f["actual_decision"], "verdict": f["verdict"],
             "evidence_class": f["evidence_class"],
             "engine_note": f.get("engine_note", ""),
             "measurement_validity": p["measurement_validity"],
             "intent_coverage": p["intent_coverage"],
             "unknown_kind": p["unknown_kind"]}
            for f, p in zip(probe_findings, per_probe)
        ],
    }


BADGE = {
    "SATISFIED": "ok", "PASS": "ok",
    "UNRESOLVED": "warn", "NOT_REPRODUCED": "warn",
    "NOT_SATISFIED": "bad", "FAIL": "bad",
    "NOT_APPLICABLE": "na",
}


def _badge(value):
    cls = BADGE.get(value, "na")
    return (f'<span class="badge {cls}">{html.escape(str(value))}</span>')


def build_scorecard(bundle, out_dir, command_repro, repro_note_suffix=""):
    """Emit scorecard.json + scorecard.html into out_dir. Returns paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    scorecard = {
        "schema_version": "fineprint-check-scorecard.v1",
        "bundle_id": bundle["bundle_id"],
        "generated_utc": generated,
        "label": bundle.get("label", ""),
        "run": bundle["run"],
        "privacy": bundle["privacy"],
        "claim_scope": bundle["claim_scope"],
        "dual_verdict_summary": bundle["dual_verdict_summary"],
        "semantics": SEMANTICS,
        "invariants": bundle["invariant_results"],
        "reproducibility": {
            "command": command_repro,
            "bundle": "bundle.json",
            "note": ("Deterministic from the sealed bundle: re-running the "
                     "command above with the same bundle reproduces this "
                     "scorecard byte-for-byte except generated_utc."
                     + repro_note_suffix),
        },
    }
    json_path = out_dir / "scorecard.json"
    json_path.write_text(json.dumps(scorecard, indent=2) + "\n")

    html_path = out_dir / "scorecard.html"
    html_path.write_text(_render_html(scorecard), encoding="utf-8")
    return json_path, html_path


def _render_html(sc):
    run = sc["run"]
    summ = sc["dual_verdict_summary"]
    claim = sc["claim_scope"]
    priv = sc["privacy"]

    rows = []
    for inv in sc["invariants"]:
        priv_tag = ' <span class="priv">private</span>' if inv["private"] \
            else ""
        layer_tag = (f'<span class="layer">{html.escape(inv["source_layer"])}'
                     f'</span>')
        probe_rows = []
        for pr in inv["probe_rows"]:
            argv = html.escape(" ".join(pr["argv"]))
            exp_set = pr.get("expected_decisions") or [pr["expected_decision"]]
            exp_txt = (" | ".join(exp_set) if len(exp_set) > 1
                       else exp_set[0])
            uk = (f' <span class="uk">{html.escape(pr["unknown_kind"])}'
                   f'</span>') if pr["unknown_kind"] else ""
            note = html.escape(pr["engine_note"]) if pr["engine_note"] else ""
            probe_rows.append(
                f"<tr><td><code>{html.escape(pr['probe_id'])}</code></td>"
                f"<td>{html.escape(pr['probe_family'])}</td>"
                f"<td><code>{argv}</code></td>"
                f"<td>{html.escape(exp_txt)}</td>"
                f"<td>{html.escape(pr['actual_decision'])}</td>"
                f"<td>{_badge(pr['verdict'].upper()) if pr['verdict'] != 'not_run' else _badge('NOT_REPRODUCED')}</td>"
                f"<td>{_badge(pr['intent_coverage'])}{uk}</td>"
                f"<td class='note'>{note}</td></tr>")
        detail = ("<details><summary>probes "
                  f"({inv['probes']['pass']} pass / {inv['probes']['fail']} "
                  f"fail / {inv['probes']['not_run']} not run)</summary>"
                  "<table class='probes'><tr><th>probe</th><th>family</th>"
                  "<th>argv</th><th>expected</th><th>actual</th><th>verdict</th>"
                  "<th>intent</th><th>note</th></tr>"
                  + "".join(probe_rows) + "</table></details>")
        rows.append(
            f"<tr><td><code>{html.escape(inv['invariant_id'])}</code>{priv_tag}"
            f"<br>{layer_tag}</td>"
            f"<td>{html.escape(inv['name'])}<br><span class='dim'>"
            f"{html.escape(inv['intent_direction'])} · "
            f"{html.escape(inv['expectation_basis'] or inv['measurement_status'])}</span></td>"
            f"<td>{_badge(inv['measurement_validity'])}</td>"
            f"<td>{_badge(inv['intent_coverage'])}</td>"
            f"<td>{detail}</td></tr>")

    mv = summ["measurement_validity"]
    ic = summ["intent_coverage"]
    uk = summ["unknown_kinds"]

    privacy_note = ""
    if priv["org_entries"] and not priv["public_mode"]:
        privacy_note = (f"<p class='privacy'>This run includes "
                        f"{priv['org_entries']} org-private invariant(s), "
                        f"flagged <span class='priv'>private</span>. They are "
                        f"part of the sealed bundle on this machine only.</p>")
    elif priv["public_mode"]:
        privacy_note = ("<p class='privacy'>Public mode: org-private entries "
                        "were stripped before sealing; this artifact names "
                        "no private invariant.</p>")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinePrint check scorecard — {html.escape(sc['label'])}</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
.badge{{display:inline-block;padding:.15em .6em;border-radius:999px;font-size:.8em;font-weight:700}}
.ok{{background:#dff5e1;color:#14532d}} .warn{{background:#fef3c7;color:#92400e}}
.bad{{background:#fee2e2;color:#991b1b}} .na{{background:#e5e7eb;color:#4b5563}}
.priv{{background:#ede9fe;color:#5b21b6;font-size:.75em;padding:.1em .5em;border-radius:4px}}
.layer{{background:#f3f4f6;color:#374151;font-size:.75em;padding:.1em .5em;border-radius:4px}}
.uk{{font-size:.75em;color:#6b7280}} .dim{{color:#6b7280;font-size:.85em}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #e5e7eb;padding:.5rem;text-align:left;vertical-align:top}}
th{{background:#f9fafb}} code{{font-size:.85em}}
details summary{{cursor:pointer;color:#1d4ed8}}
.note{{font-size:.8em;color:#4b5563;max-width:320px}}
.stat{{display:inline-block;margin:.25rem 1.5rem .25rem 0}}
.privacy{{background:#faf5ff;border:1px solid #ddd6fe;padding:.75rem;border-radius:8px}}
.claim{{background:#f0fdf4;border:1px solid #bbf7d0;padding:.75rem;border-radius:8px}}
footer{{margin-top:2rem;color:#6b7280;font-size:.85em;border-top:1px solid #e5e7eb;padding-top:1rem}}
</style></head><body>
<h1>FinePrint check scorecard</h1>
<p class="dim">run <code>{html.escape(sc['bundle_id'])}</code> · label
<strong>{html.escape(sc['label'])}</strong> · {html.escape(sc['generated_utc'])} ·
harness <strong>{html.escape(run['harness'])}</strong> ({html.escape(run['measurement_route'])},
{html.escape(run['evidence_class'])}) · policy
<code>{html.escape(run['policy']['path'])}</code></p>
{privacy_note}
<div class="claim"><strong>Claim scope (measured-before-claimed):</strong>
{claim['measured_invariants']} measured invariants —
{_badge('SATISFIED')} × {claim['measured_satisfied']},
{_badge('UNRESOLVED')} × {claim['measured_unresolved']},
{_badge('NOT_SATISFIED')} × {claim['measured_not_satisfied']}.
{claim['exploratory_invariants']} exploratory (UNMEASURED) invariants below
carry no conformance claim.</div>
<h2>Dual verdicts (per invariant)</h2>
<p><span class="stat"><strong>measurement:</strong> PASS {mv['PASS']} · FAIL {mv['FAIL']} ·
NOT_REPRODUCED {mv['NOT_REPRODUCED']}</span>
<span class="stat"><strong>intent:</strong> SATISFIED {ic['SATISFIED']} ·
NOT_SATISFIED {ic['NOT_SATISFIED']} · UNRESOLVED {ic['UNRESOLVED']} ·
NOT_APPLICABLE {ic['NOT_APPLICABLE']}</span></p>
<p class="dim">unknown kinds — no-rule-match: {uk['no-rule-match']};
insufficient-runtime-evidence: {uk['insufficient-runtime-evidence']};
unsupported-adapter: {uk['unsupported-adapter']}. A correctly reported
unknown is measurement PASS (when expected) but never a satisfied
invariant.</p>
<table><tr><th>invariant</th><th>name</th><th>measurement</th><th>intent</th>
<th>probes</th></tr>
{''.join(rows)}
</table>
<h2>Semantics</h2>
<ul>
<li><strong>measurement_validity:</strong> {html.escape(SEMANTICS['measurement_validity'])}</li>
<li><strong>intent_coverage:</strong> {html.escape(SEMANTICS['intent_coverage'])}</li>
<li><strong>observed_effect:</strong> {html.escape(SEMANTICS['observed_effect'])}</li>
</ul>
<footer><strong>Reproducibility.</strong> This scorecard is deterministic from
the sealed bundle: <code>{html.escape(sc['reproducibility']['command'])}</code>
reproduces it byte-for-byte except the timestamp. Bundle:
<code>bundle.json</code> (Merkle-sealed).</footer>
</body></html>
"""


def main(argv):
    if "--bundle" not in argv or "--out" not in argv:
        sys.exit("usage: check_scorecard.py --bundle <bundle.json> "
                 "--out <dir>")
    bundle = json.loads(Path(argv[argv.index("--bundle") + 1]).read_text())
    out = Path(argv[argv.index("--out") + 1])
    repro = ("python3 tools/check_scorecard.py --bundle <bundle.json> "
             "--out <dir>")
    jp, hp = build_scorecard(bundle, out, repro)
    print(f"wrote {jp}\n      {hp}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
