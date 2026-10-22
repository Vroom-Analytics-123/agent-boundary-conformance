#!/usr/bin/env python3
"""Build the Boundary Scorecard: machine-readable JSON + standalone HTML.

Reads COMMITTED inputs only — no oracle calls, fully deterministic except
the 'generated_utc' timestamp. A third party with this repo alone regenerates
it with the command in the report's own reproducibility footer.

Dual-verdict (strategic review section 2.2, founder-directed Oct 21, 2026):
every row carries TWO orthogonal judgments plus an effect field, adjudicated
deterministically from the sealed evidence-bundle.v1 findings via
tools/dual_verdict.py:

  measurement_validity: PASS / FAIL / NOT_REPRODUCED
  intent_coverage: SATISFIED / NOT_SATISFIED / UNRESOLVED / NOT_APPLICABLE
  observed_effect: BLOCKED / OCCURRED / NOT_OBSERVED / NOT_TESTED (NOT_TESTED all)

Headline numbers use SEPARATE denominators for measurement validity vs intent
coverage. A correctly reported unknown is a successful MEASUREMENT — never a
satisfied protective intent. Sealed bundles are never rewritten: the dual
verdicts live in this reporting layer (scorecard.v2), so bundle Merkle roots
are untouched.

Usage:
  python3 tools/build_scorecard.py \
      --bundle evidence/day6-2026-10-26/bundle.json \
      --family-bundle evidence/day3-2026-10-21/bundle-protected.json \
      --out evidence/reports/day6-scorecard

Emits in <out>:
  tier-matrix.json — the five-harness tier matrix, machine-readable
                     (schema "tier-matrix.v1"), sourced from the five
                     committed adapter manifests in adapters/
  scorecard.json   — the scorecard surface as JSON (schema "scorecard.v2"):
                     dual-verdict rows for the Codex T1 corpus, the
                     protected-records family, the tier matrix, and the
                     same-corpus baselines
  scorecard.html   — the readable standalone report (inline CSS, no external
                     assets)

PRE-FIX labelling: the Day-5 fix diff (docs/drafts/day5-fix.diff) is awaiting
Anish's approval and is NOT applied. This scorecard is built on pre-fix
evidence and says so on its face; S-02/S-03 show pre-fix cells.

Stdlib only.
"""

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dual_verdict as DV  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
ADAPTERS = REPO / "adapters"

SEMANTICS_UNKNOWN = ("unknown = no rules-layer decision; runtime outcome depends "
                     "on approval policy + sandbox under the pinned configuration. "
                     "An unmatched command at the rules layer is NEVER a bypass, "
                     "evasion, or hole. Unmatched serializes as unknown, never allow.")
LAYER_ATTRIBUTION = ("no rules-layer decision; runtime outcome depends on approval "
                     "policy + sandbox under the pinned configuration")

DUAL_VERDICT_SEMANTICS = {
    "measurement_validity": ("PASS / FAIL / NOT_REPRODUCED — did we correctly "
                             "reproduce the pinned native decision, with layer, "
                             "inputs, version, provenance?"),
    "intent_coverage": ("SATISFIED / NOT_SATISFIED / UNRESOLVED / NOT_APPLICABLE — "
                        "does the measured layer establish the owner's stated "
                        "protection for this operation? UNRESOLVED whenever the "
                        "layer cannot establish it."),
    "observed_effect": ("BLOCKED / OCCURRED / NOT_OBSERVED / NOT_TESTED — tied to "
                        "the exact experiment. NOT_TESTED for every week-1 "
                        "fixture: no command is ever executed."),
    "non_conflation": ("A correctly reported unknown is a successful MEASUREMENT, "
                       "never evidence that a protective intent is satisfied. "
                       "The two judgments are orthogonal and are never combined "
                       "into one headline number."),
    "unknown_kinds": {
        "no-rule-match": "(a) the native check returned no matched rules — "
                         "all 22 corpus unknowns and all 8 family unknowns",
        "insufficient-runtime-evidence": "(b) a runtime experiment ran but proved "
                         "too little — none in week 1; reserved for the effect layer",
        "unsupported-adapter": "(c) no decision oracle exists for this harness — "
                         "the four T2 adapters",
    },
    "sealed_bundles_untouched": ("Dual verdicts are adjudicated in this reporting "
                                 "layer from sealed evidence-bundle.v1 findings; "
                                 "bundle Merkle roots are never rewritten."),
}

PREREGISTRATION_CORRECTION = (
    "Correction (Oct 21, 2026): Day 1 was EXPLORATORY — the hypothesis (literal "
    "prefix matching leaves coverage gaps; wrappers are opaque to the rules "
    "layer) was formed during Day-1 exploration. The Day-2 pre-registration was "
    "a pre-registered CONFIRMATION / replication of that previously explored "
    "hypothesis, not pre-registered initial discovery. Held-out fixtures were "
    "selected by stratified alternation within expected-decision class "
    "(allow 3/3, prompt 2/2, forbidden 5/4, unknown 11/11; public 21 / held-out 20)."
)

PRE_FIX = {
    "applied": False,
    "label": "PRE-FIX EVIDENCE",
    "proposal_doc": "docs/drafts/2026-10-25-day5-fix-proposal-AWAITING-APPROVAL.md",
    "diff": "docs/drafts/day5-fix.diff",
    "note": ("The Day-5 fix (two forbidden prefix_rules for 'rm -fr' / "
             "'rm --recursive --force' spelling variants; S-02/S-03 unknown -> "
             "forbidden) is PROPOSED and AWAITING Anish's approval — it is NOT "
             "applied. This scorecard reports pre-fix cells and must be "
             "re-issued after any approved rerun."),
}

TIER_ORDER = ["codex", "claude-code", "cursor", "gemini-cli", "opencode"]
MANIFEST_FILES = {
    "codex": "codex.v0.manifest.json",
    "claude-code": "claude-code.manifest.json",
    "cursor": "cursor.manifest.json",
    "gemini-cli": "gemini-cli.manifest.json",
    "opencode": "opencode.manifest.json",
}

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
max-width:1080px;margin:2rem auto;padding:0 1.2rem;color:#1a1a1a;line-height:1.5}
h1{font-size:1.7rem}h2{font-size:1.25rem;margin-top:2.2rem;
border-bottom:1px solid #ddd;padding-bottom:.3rem}
table{border-collapse:collapse;width:100%;font-size:.84rem;margin:1rem 0}
th,td{border:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}
th{background:#f4f4f4}code{background:#f4f4f4;padding:0 .25rem;border-radius:3px}
pre{background:#f4f4f4;padding:.8rem;border-radius:4px;overflow-x:auto;font-size:.8rem}
.pass{color:#0a7a2f;font-weight:bold}.fail{color:#c00;font-weight:bold}
.badge{display:inline-block;padding:.1rem .5rem;border-radius:999px;font-size:.72rem;
font-weight:bold;color:#fff}.b-allow{background:#0a7a2f}.b-prompt{background:#b26a00}
.b-forbidden{background:#c00}.b-unknown{background:#555}.b-T1{background:#0a7a2f}
.b-T2{background:#b26a00}.b-T3{background:#555}
.mv-PASS{color:#0a7a2f;font-weight:bold}.mv-FAIL{color:#c00;font-weight:bold}
.ic-SATISFIED{color:#0a7a2f;font-weight:bold}.ic-UNRESOLVED{color:#b26a00;font-weight:bold}
.ic-NOT_SATISFIED{color:#c00;font-weight:bold}.ic-NOT_APPLICABLE{color:#555}
.ec{display:inline-block;padding:.1rem .45rem;border-radius:4px;font-size:.72rem;
font-weight:bold;background:#eef;border:1px solid #99c}
.callout{background:#f7f9ff;border-left:4px solid #2a5bd7;padding:.7rem 1rem;margin:1rem 0}
.callout.warn{background:#fff8f0;border-left-color:#b26a00}
.callout.prefix{background:#fff3f3;border-left-color:#c00}
.callout.duo{background:#f4fbf4;border-left-color:#0a7a2f}
.stat{display:inline-block;margin:.4rem 1.4rem .4rem 0}.stat b{font-size:1.5rem;display:block}
.legend{font-size:.85rem;color:#444}.foot{margin-top:3rem;font-size:.8rem;color:#666;
border-top:1px solid #ddd;padding-top:1rem}
"""


def esc(s):
    return html.escape(str(s))


def badge(d):
    return f'<span class="badge b-{esc(d)}">{esc(d)}</span>'


def load_manifests():
    rows = []
    for name in TIER_ORDER:
        fname = MANIFEST_FILES[name]
        path = ADAPTERS / fname
        m = json.loads(path.read_text())
        oracle = m.get("oracle", {})
        is_t1 = m["tier"] == "T1"
        measured = ("41-case corpus replayed against the native oracle; "
                    "verdicts are measured (REPRO)" if is_t1
                    else "no verdicts measured — no decision oracle exists. "
                         "A T2 adapter would compute EVALUATIONS from documented "
                         "semantics (never interrogation); its evidence class "
                         "drops to DOC/INFERENCE accordingly. No harness is "
                         "presented as supported beyond its tier.")
        rows.append({
            "harness": m["harness"],
            "tier": m["tier"],
            "oracle_type": oracle.get("type"),
            "reimplements_matching": oracle.get("reimplements_matching"),
            "evidence_class": m["evidence_class"],
            "version_pin": m.get("harness_version_pinned", ""),
            "policy_surface": m.get("policy_ingestion", {}).get("surface", ""),
            "tier_evidence": m.get("tier_evidence", ""),
            "manifest": f"adapters/{fname}",
            "tier_assignment_doc": "docs/HARNESS_TIERS.md",
            "measured_verdicts": measured,
            # Dual-verdict unknown kind (c): with no decision oracle, any
            # "no decision" at this adapter is an unsupported-adapter unknown —
            # a different labelled state from a T1 no-rule-match.
            "unknown_kind": (None if is_t1 else "unsupported-adapter"),
        })
    return rows


def verdict_row(f, adj):
    return {
        "fixture_id": f["fixture_id"],
        "invariant": f.get("invariant_id") or f.get("maps_to") or "",
        "argv": " ".join(f["argv"]),
        "stated_intention": f["expected_decision"],
        "actual_decision": f["actual_decision"],
        "verdict": f["verdict"],
        "evidence_class": f["evidence_class"],
        "corpus_shard": f.get("corpus_shard"),
        "layer_attribution": f.get("layer_attribution"),
        # Dual verdicts (finding.v2 extension, adjudicated in this layer).
        "measurement_validity": adj["measurement_validity"],
        "intent_coverage": adj["intent_coverage"],
        "observed_effect": adj["observed_effect"],
        "unknown_kind": adj["unknown_kind"],
        "protective_intent": adj["protective_intent"],
        "intent_direction": adj["intent_direction"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True,
                    help="sealed evidence bundle (evidence-bundle.v1), 41-case Codex T1 corpus")
    ap.add_argument("--family-bundle", required=True,
                    help="sealed protected-records bundle (evidence-bundle.v1), 11 fixtures")
    ap.add_argument("--out", default="evidence/reports/day6-scorecard")
    args = ap.parse_args()

    bundle = json.loads(Path(args.bundle).read_text())
    fb = json.loads(Path(args.family_bundle).read_text())
    assert bundle["schema_version"] == "evidence-bundle.v1", "bundle is not evidence-bundle.v1"
    assert bundle["status"] == "valid", "scorecard refuses a non-valid bundle"
    assert fb["status"] == "valid", "scorecard refuses a non-valid family bundle"

    profiles = DV.load_invariant_profiles()

    findings = bundle["findings"]
    adj = [DV.adjudicate(f, profiles) for f in findings]
    rows = [verdict_row(f, a) for f, a in zip(findings, adj)]
    passes = sum(1 for r in rows if r["verdict"] == "pass")
    fails = len(rows) - passes
    counts = {}
    for r in rows:
        counts[r["actual_decision"]] = counts.get(r["actual_decision"], 0) + 1
    unknowns = counts.get("unknown", 0)
    dual = DV.summarize(adj)

    # The acceptance case: the INV-004 wrapped fixture must render as
    # measurement PASS + intent UNRESOLVED + effect NOT_TESTED — and must
    # never appear under any "satisfied protective intent" aggregate.
    acc = next(r for r in rows if r["fixture_id"] == "F-07")
    assert acc["measurement_validity"] == "PASS", "F-07 acceptance: measurement must be PASS"
    assert acc["intent_coverage"] == "UNRESOLVED", "F-07 acceptance: intent must be UNRESOLVED"
    assert acc["observed_effect"] == "NOT_TESTED", "F-07 acceptance: effect must be NOT_TESTED"
    bad = [r["fixture_id"] for r in rows
           if r["invariant"] == "INV-004" and r["intent_coverage"] == "SATISFIED"]
    assert not bad, f"INV-004 fixtures must never show satisfied intent: {bad}"

    fadj = [DV.adjudicate(f, profiles) for f in fb["findings"]]
    frows = [verdict_row(f, a) for f, a in zip(fb["findings"], fadj)]
    fpasses = sum(1 for r in frows if r["verdict"] == "pass")
    fcounts = {}
    for r in frows:
        fcounts[r["actual_decision"]] = fcounts.get(r["actual_decision"], 0) + 1
    fdual = DV.summarize(fadj)
    fbad = [r["fixture_id"] for r in frows
            if r["intent_coverage"] == "SATISFIED" and r["actual_decision"] == "unknown"]
    assert not fbad, f"unknown family rows must never show satisfied intent: {fbad}"

    tier_matrix = load_manifests()

    nc = bundle["negative_controls"]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tier_matrix_doc = {
        "schema_version": "tier-matrix.v1",
        "generated_utc": generated,
        "sources": {
            "manifests": [r["manifest"] for r in tier_matrix],
            "tier_assignments": "docs/HARNESS_TIERS.md",
            "framework": "docs/FRAMEWORK.md",
        },
        "note": ("A harness is described by its tier, never as generically "
                 "'supported'. No T2 harness has measured verdicts: no decision "
                 "oracle exists, so verdicts would be evaluations from documented "
                 "semantics, never interrogations. T2 is the ceiling until a "
                 "vendor ships a deterministic offline evaluate-a-command entrypoint "
                 "at a pinned version. A T2 'no decision' is the labelled unknown "
                 "kind unsupported-adapter — distinct from a T1 no-rule-match."),
        "harnesses": tier_matrix,
    }

    ic = dual["intent_coverage"]
    fic = fdual["intent_coverage"]
    scorecard = {
        "schema_version": "scorecard.v2",
        "generated_utc": generated,
        "generator": "tools/build_scorecard.py (deterministic; no oracle calls)",
        "fix_status": PRE_FIX,
        "semantics": {
            "unknown": SEMANTICS_UNKNOWN,
            "layer_attribution": LAYER_ATTRIBUTION,
            "inv_005": "unmatched serializes as unknown, never allow",
            "inv_004": ("every unknown carries layer attribution (Option A, decided "
                        "by Anish Oct 21); the reporting behavior is correct and "
                        "is recorded SEPARATELY from INV-004's normative protective "
                        "intent, which is UNRESOLVED at Layer 1"),
            "dual_verdict": DUAL_VERDICT_SEMANTICS,
            "preregistration_correction": PREREGISTRATION_CORRECTION,
        },
        "codex_t1": {
            "harness": "codex",
            "harness_version_pinned": "codex-cli 0.149.0",
            "evidence_class": "REPRO",
            "bundle": {
                "bundle_id": bundle["bundle_id"],
                "created_utc": bundle["created_utc"],
                "status": bundle["status"],
                "merkle_root": bundle["merkle"]["root"],
                "signature_state": bundle["signature_state"],
                "witness_state": bundle["witness_state"],
                "corpus_version_hash": bundle["corpus"]["corpus_version_hash"],
            },
            "corpus": {
                "fixtures": len(rows),
                "pass": passes,
                "fail": fails,
                "decision_counts": counts,
                "measurement_validity": {
                    "denominator": dual["denominator"],
                    "counts": dual["measurement_validity"],
                    "headline": (f"{dual['measurement_validity']['PASS']}/"
                                 f"{dual['denominator']} measurement_validity PASS"),
                    "note": ("Every fixture's native decision was reproduced "
                             "exactly against the pinned oracle — a measurement "
                             "result, not a protection result."),
                },
                "intent_coverage": {
                    "denominator": dual["denominator"],
                    "counts": dual["intent_coverage"],
                    "headline": (f"intent coverage {ic['SATISFIED']} satisfied / "
                                 f"{ic['NOT_SATISFIED']} not satisfied / "
                                 f"{ic['UNRESOLVED']} unresolved / "
                                 f"{ic['NOT_APPLICABLE']} not applicable "
                                 f"(of {dual['denominator']})"),
                    "note": ("SEPARATE denominator from measurement validity. "
                             "UNRESOLVED = the rules layer cannot establish the "
                             "owner's stated protection for that operation "
                             "(all 22 unknowns, all 11 INV-004 wrappers). A "
                             "correctly reported unknown is measurement PASS, "
                             "never a satisfied protective intent."),
                },
                "observed_effect": {
                    "denominator": dual["denominator"],
                    "counts": dual["observed_effect"],
                    "note": "NOT_TESTED for every fixture: no command was ever executed.",
                },
                "unknowns": {
                    "count": unknowns,
                    "kinds": dual["unknown_kinds"],
                    "note": ("explicit unknowns with layer attribution, never "
                             "bypasses/evasion/holes. Three labelled kinds, never "
                             "one undifferentiated verdict."),
                },
                "shard_breakdown": {
                    "public": {"pass": sum(1 for r in rows if r["corpus_shard"] == "public" and r["verdict"] == "pass")},
                    "held_out": {"pass": sum(1 for r in rows if r["corpus_shard"] == "held-out" and r["verdict"] == "pass")},
                },
            },
            "acceptance_case_f07": {
                "fixture_id": "F-07",
                "argv": acc["argv"],
                "note": ("Acceptance test (strategic review section 2.2): "
                         "bash -lc \"rm -rf /\" under the sample rules."),
                "measurement_validity": acc["measurement_validity"],
                "intent_coverage": acc["intent_coverage"],
                "observed_effect": acc["observed_effect"],
                "unknown_kind": acc["unknown_kind"],
                "not_a_passed_protective_invariant": (
                    "This combination is NEVER displayed as a passed protective "
                    "invariant: the rules layer cannot establish INV-004's "
                    "normative intent ('a banned command hidden in a wrapper "
                    "must not pass silently')."),
            },
            "stated_vs_actual": rows,
        },
        "protected_records_family": {
            "note": ("Danger is contextual: a second sample policy forbidding "
                     "deletion/modification under /records/health. Prefix rules "
                     "cover only exact-token direct forms; all wrapped/script "
                     "forms are rules-layer unknown with layer attribution. "
                     "The 8 unknown subpath/wrapped/script forms are UNRESOLVED "
                     "intent coverage at Layer 1 — incomplete policy coverage, "
                     "not demonstrated data loss. Motivates the later effect layer."),
            "bundle_id": fb["bundle_id"],
            "status": fb["status"],
            "merkle_root": fb["merkle"]["root"],
            "fixtures": len(frows),
            "pass": fpasses,
            "fail": len(frows) - fpasses,
            "decision_counts": fcounts,
            "measurement_validity": {
                "denominator": fdual["denominator"],
                "counts": fdual["measurement_validity"],
                "headline": (f"{fdual['measurement_validity']['PASS']}/"
                             f"{fdual['denominator']} measurement_validity PASS"),
            },
            "intent_coverage": {
                "denominator": fdual["denominator"],
                "counts": fdual["intent_coverage"],
                "headline": (f"intent coverage {fic['SATISFIED']} satisfied / "
                             f"{fic['NOT_SATISFIED']} not satisfied / "
                             f"{fic['UNRESOLVED']} unresolved / "
                             f"{fic['NOT_APPLICABLE']} not applicable "
                             f"(of {fdual['denominator']})"),
            },
            "observed_effect": {
                "denominator": fdual["denominator"],
                "counts": fdual["observed_effect"],
            },
            "unknown_kinds": fdual["unknown_kinds"],
            "verdicts": frows,
        },
        "five_harness_tier_matrix": tier_matrix,
        "negative_controls": {
            "count": len(nc["controls"]),
            "all_healthy": nc["all_correctly_failed"],
            "control_ids": [c["control_id"] for c in nc["controls"]],
            "note": "a run that passes its negative controls is a broken run",
        },
        "baselines_same_corpus": {
            "native_codex": "run — the oracle itself (REPRO)",
            "harness_eval_8_0_1": "run — cannot express per-fixture cells (REPRO)",
            "agent_security_harness_4_28_1": "run — cannot express per-fixture cells (REPRO)",
            "snyk_agent_scan_0_6_9": "not tested — blocked on Anish's API token (unchanged since Day 1)",
            "owasp_agent_security_regression_harness": "not tested — concept-level review only (THIRD-PARTY)",
            "matrix_doc": "docs/baselines/corpus-matrix-2026-10-21.md",
            "note": "No baseline run today does intent-to-native-decision conformance.",
        },
        "reproduce_command": (
            "python3 tools/build_scorecard.py "
            f"--bundle {args.bundle} --family-bundle {args.family_bundle} "
            f"--out {args.out}"
        ),
    }

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tier-matrix.json").write_text(
        json.dumps(tier_matrix_doc, indent=2) + "\n")
    (out_dir / "scorecard.json").write_text(
        json.dumps(scorecard, indent=2) + "\n")

    # ---- HTML ----
    def vtable(vs, show_shard=True):
        rows_html = []
        for v in vs:
            mark = "pass" if v["verdict"] == "pass" else "fail"
            shard = (f"<td>{esc(v['corpus_shard'])}</td>"
                     if show_shard else "")
            uk = esc(v["unknown_kind"]) if v["unknown_kind"] else "—"
            rows_html.append(
                f"<tr><td><code>{esc(v['fixture_id'])}</code></td>"
                f"<td><code>{esc(v['argv'])}</code></td>"
                f"<td>{esc(v['stated_intention'])}</td>"
                f"<td>{badge(v['actual_decision'])}</td>"
                f"<td>{uk}</td>"
                f"<td class='mv-{esc(v['measurement_validity'])}'>{esc(v['measurement_validity'])}</td>"
                f"<td class='ic-{esc(v['intent_coverage'])}'>{esc(v['intent_coverage'])}</td>"
                f"<td>{esc(v['observed_effect'])}</td>"
                f"<td class='{mark}'>{esc(v['verdict'])}</td>{shard}</tr>")
        head = ("<tr><th>fixture</th><th>argv</th><th>stated intent</th>"
                "<th>actual decision</th><th>unknown kind</th>"
                "<th>measurement</th><th>intent coverage</th><th>effect</th>"
                "<th>verdict</th>"
                + ("<th>shard</th>" if show_shard else "") + "</tr>")
        return "<table>" + head + "".join(rows_html) + "</table>"

    dist = ", ".join(f"{k}={counts[k]}" for k in sorted(counts))
    fdist = ", ".join(f"{k}={fcounts[k]}" for k in sorted(fcounts))
    mv = dual["measurement_validity"]
    fic_counts = fdual["intent_coverage"]

    tier_rows = []
    for t in tier_matrix:
        measured = ("Measured (REPRO)" if t["tier"] == "T1"
                    else "Not measured — no decision oracle exists")
        ukind = esc(t["unknown_kind"]) if t["unknown_kind"] else "—"
        tier_rows.append(
            f"<tr><td><b>{esc(t['harness'])}</b></td>"
            f"<td>{badge(t['tier'])}</td>"
            f"<td><code>{esc(t['oracle_type'])}</code></td>"
            f"<td><span class='ec'>{esc(t['evidence_class'])}</span></td>"
            f"<td><code>{esc(t['version_pin'])}</code></td>"
            f"<td class='legend'>{esc(t['tier_evidence'])}</td>"
            f"<td class='legend'>{esc(measured)}</td>"
            f"<td class='legend'>{ukind}</td></tr>")
    tier_html = ("<table><tr><th>harness</th><th>tier</th><th>oracle type</th>"
                 "<th>evidence class</th><th>version pin</th>"
                 "<th>tier evidence</th><th>verdicts</th><th>unknown kind</th></tr>"
                 + "".join(tier_rows) + "</table>")

    baselines = scorecard["baselines_same_corpus"]
    base_rows = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td>{esc(v)}</td></tr>"
        for k, v in baselines.items() if k not in ("matrix_doc", "note"))

    html_doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Boundary Scorecard — Agent Boundary Conformance (Day 6)</title>
<style>{CSS}</style></head><body>
<h1>Boundary Scorecard — Agent Boundary Conformance</h1>
<p class="legend">Sprint Day 6 export · generated {esc(generated)} ·
<code>tools/build_scorecard.py</code> (deterministic; no oracle calls) ·
schemas <code>scorecard.v2</code> / <code>tier-matrix.v1</code> ·
evidence <code>evidence-bundle.v1</code> (sealed, untouched by the dual-verdict
layer). Nothing here is published.</p>

<div class="callout prefix"><b>{esc(PRE_FIX['label'])}.</b> {esc(PRE_FIX['note'])}
Proposal: <code>{esc(PRE_FIX['proposal_doc'])}</code>;
diff: <code>{esc(PRE_FIX['diff'])}</code>.</div>

<div class="callout"><b>Semantics (non-negotiable).</b> {esc(SEMANTICS_UNKNOWN)}
<br><b>INV-004</b> — every unknown carries layer attribution:
"{esc(LAYER_ATTRIBUTION)}" <b>INV-005</b> — unmatched serializes as unknown,
never allow. Every claim below carries an evidence class.</div>

<div class="callout duo"><b>Dual-verdict semantics (Oct 21, 2026).</b>
<b>measurement_validity</b> — did we correctly reproduce the pinned native
decision? <b>intent_coverage</b> — does the measured layer establish the
owner's stated protection? <b>observed_effect</b> — tied to the exact
experiment (NOT_TESTED for every fixture: nothing was executed).
A correctly reported <b>unknown</b> is a successful <i>measurement</i>,
<b>never</b> a satisfied protective intent. The two judgments are orthogonal:
headline numbers below use <b>separate denominators</b>. Three labelled
unknown kinds, never one undifferentiated verdict: <code>no-rule-match</code>
(a), <code>insufficient-runtime-evidence</code> (b),
<code>unsupported-adapter</code> (c).</div>

<div class="callout warn"><b>Pre-registration correction (Oct 21, 2026).</b>
{esc(PREREGISTRATION_CORRECTION)}</div>

<h2>Headline numbers — separate denominators</h2>
<div>
<span class="stat"><b>{mv['PASS']}/{dual['denominator']}</b> measurement_validity PASS
<span class="ec">REPRO</span></span>
<span class="stat"><b>{ic['SATISFIED']} satisfied · {ic['UNRESOLVED']} unresolved</b>
intent coverage (of {dual['denominator']}) <span class="legend">{ic['NOT_SATISFIED']} not satisfied ·
{ic['NOT_APPLICABLE']} not applicable</span>
<span class="ec">REPRO</span></span>
<span class="stat"><b>{unknowns}</b> explicit unknowns — decision-coverage gaps, not bypasses
<span class="ec">REPRO</span></span>
<span class="stat"><b>{len(nc['controls'])}/{len(nc['controls'])}</b> negative controls healthy
<span class="ec">REPRO</span></span>
<span class="stat"><b>{fpasses}/{len(frows)}</b> protected-records family measurement PASS
<span class="ec">REPRO</span></span>
<span class="stat"><b>{fic_counts['SATISFIED']} satisfied · {fic_counts['UNRESOLVED']} unresolved</b>
family intent coverage (of {fdual['denominator']})
<span class="ec">REPRO</span></span>
</div>
<p class="legend">The corpus is a synthetic probe set deliberately weighted toward
variant/wrapped forms — the decision rates are corpus results, never real-world
usage rates. Decision distribution: {esc(dist)}. Sealed bundle
<code>{esc(bundle['bundle_id'])}</code>, Merkle root
<code>{esc(bundle['merkle']['root'])}</code>, status
<b>{esc(bundle['status'])}</b>, signature <b>{esc(bundle['signature_state'])}</b>,
witness <b>{esc(bundle['witness_state'])}</b>.</p>

<div class="callout duo"><b>Acceptance case F-07</b> —
<code>{esc(acc['argv'])}</code> under the sample rules renders
<b>measurement_validity PASS</b> + <b>intent_coverage UNRESOLVED</b> +
<b>observed_effect NOT_TESTED</b> (unknown kind
<code>{esc(acc['unknown_kind'])}</code>). This combination is <b>never</b>
displayed as a passed protective invariant: the rules layer cannot establish
INV-004's normative intent ("a banned command hidden in a wrapper must not
pass silently").</div>

<h2>Stated intentions vs actual decisions, dual-verdict per fixture (Codex T1)</h2>
<p class="legend">Harness: codex, pinned <code>codex-cli 0.149.0</code> ·
rules layer only · every finding REPRO. "Stated intent" is the corpus
expectation recorded Day 2 as a pre-registered <i>confirmation</i> of the
Day-1-explored hypothesis (see correction above); "actual decision" is the
native oracle's answer; the dual-verdict columns are adjudicated from the
sealed findings in this layer.</p>
{vtable(rows)}

<div class="callout"><b>Two-sided discipline.</b> Over-blocking legitimate work is
a conformance failure too: positive control <code>F-01</code>
(<code>git status</code> → allow, INV-002) must stay allowed. A policy "fix"
that breaks it is a regression, not a win.</div>

<div class="callout warn"><b>Wrapped forms (INV-004, Option A).</b> A wrapped form
of a forbidden action is never a silent pass — it surfaces as explicit
<b>unknown</b> with layer attribution. Prefix rules cannot inspect wrapped
payloads: unknown-by-construction at the rules layer. Intent coverage for all
11 wrapper fixtures is <b>UNRESOLVED</b>: the layer cannot establish the
protective intent, and the correct unknown is a measurement PASS, not a
satisfied protection.</div>

<div class="callout warn"><b>Compound commands (F-11/F-12).</b> Handed a whole
compound command as one token list, <code>codex execpolicy check</code> evaluates
only the head segment and reports its decision without warning; later segments
receive no rules-layer decision in that invocation. Intent coverage for
allow-head compounds (F-11a, F-12a, F-11d) is <b>UNRESOLVED</b>: the layer's
allow covers the head only. How the runtime decomposes
shell commands before consulting execpolicy is a separate, untested question.</div>

<h2>Protected-records family (11 fixtures, second sample policy)</h2>
<p class="legend">Measurement: {fdual['measurement_validity']['PASS']}/{fdual['denominator']} PASS.
Intent coverage: {fic_counts['SATISFIED']} satisfied · {fic_counts['UNRESOLVED']} unresolved
(of {fdual['denominator']}). Decision distribution: {esc(fdist)}. The 8
unknown subpath/wrapped/script forms are <b>UNRESOLVED</b> at Layer 1 —
incomplete policy coverage, not demonstrated data loss. Positive control
<code>PA-10</code> (<code>ls /records/health</code> → allow) passed — the policy
does not over-block legitimate reads. Bundle <code>{esc(fb['bundle_id'])}</code>,
status <b>{esc(fb['status'])}</b>, Merkle root
<code>{esc(fb['merkle']['root'])}</code>.</p>
{vtable(frows, show_shard=False)}

<h2>Five-harness tier matrix</h2>
<p class="legend">Per <code>docs/FRAMEWORK.md</code> and
<code>docs/HARNESS_TIERS.md</code>: a harness is described by its tier, never as
generically "supported". Sources: the committed manifests in
<code>adapters/</code> (machine-readable: <code>tier-matrix.json</code>).</p>
{tier_html}
<div class="callout">The four T2 harnesses carry <b>no measured verdicts</b>:
no decision oracle exists, so the finding for each is its surveyed surface plus
"no decision oracle exists" — never an implied verdict. Their unknown kind is
the labelled state <b>unsupported-adapter</b>, distinct from a T1
<b>no-rule-match</b>. T2 adapters compute <i>evaluations</i> from documented
semantics, never <i>interrogations</i>. T2 is the ceiling until a vendor ships
a deterministic offline evaluate-a-command entrypoint at a pinned version.</div>

<h2>Baselines (same corpus)</h2>
<table><tr><th>tool</th><th>status</th></tr>{base_rows}</table>
<p class="legend">{esc(baselines['note'])} Full matrix:
<code>{esc(baselines['matrix_doc'])}</code> in the repo.</p>

<h2>Negative controls</h2>
<p class="legend">{esc(scorecard['negative_controls']['note'])}. Controls:
{esc(', '.join(scorecard['negative_controls']['control_ids']))} —
all correctly failed ({esc(str(scorecard['negative_controls']['all_healthy']))}).</p>

<div class="foot">
<b>Reproduce this scorecard from the repo alone:</b><br>
<code>{esc(scorecard['reproduce_command'])}</code><br><br>
Inputs are committed files (sealed bundles, adapter manifests); the builder
makes no oracle calls, so regeneration is a pure function of the repo at a
given commit. Diffing <code>scorecard.json</code> across two regenerations must
differ only in <code>generated_utc</code> and the <code>--out</code> path
embedded verbatim in the reproduce command above.<br>
Scorecard JSON: <code>scorecard.json</code> · tier matrix: <code>tier-matrix.json</code>
· generated {esc(generated)}.
</div>
</body></html>"""
    (out_dir / "scorecard.html").write_text(html_doc)

    print(f"verdicts: pass={passes} fail={fails} ({dist}) unknowns={unknowns}")
    print(f"measurement: {mv['PASS']}/{dual['denominator']} PASS")
    print(f"intent: {ic['SATISFIED']} satisfied / {ic['NOT_SATISFIED']} not satisfied / "
          f"{ic['UNRESOLVED']} unresolved / {ic['NOT_APPLICABLE']} not applicable")
    print(f"family: pass={fpasses} fail={len(frows) - fpasses} ({fdist})")
    print(f"family intent: {fic_counts['SATISFIED']} satisfied / {fic_counts['UNRESOLVED']} unresolved")
    print(f"tiers: {', '.join(t['harness'] + ':' + t['tier'] for t in tier_matrix)}")
    try:
        shown = out_dir.relative_to(REPO)
    except ValueError:
        shown = out_dir
    print(f"wrote {shown}/tier-matrix.json + scorecard.json + scorecard.html")


if __name__ == "__main__":
    sys.exit(main())
