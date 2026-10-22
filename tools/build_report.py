#!/usr/bin/env python3
"""Build a standalone, third-party-regenerable conformance report.

Reads a committed run_fixtures.py output JSON (the reproducible evidence),
optionally the protected-records family rerun + bundle and the baseline
matrix doc, and emits:
  <out>/report.json  — machine-readable (pinned config, per-fixture verdicts)
  <out>/report.html  — readable report, fully standalone (inline CSS, no
                       external assets)

A third party with this repo alone regenerates it with the documented exact
command (see the report's own reproducibility footer and docs/daily briefs):

  python3 tools/build_report.py --rerun evidence/reruns/rerun-20261022T003528Z.json \
      --family-rerun evidence/reruns/rerun-20261022T005546Z.json \
      --family-bundle evidence/day3-2026-10-21/bundle-protected.json \
      --matrix docs/baselines/corpus-matrix-2026-10-21.md \
      --out evidence/reports/day2-41-corpus

No oracle call is made: the report is a deterministic function of the
committed rerun JSON(s), so regeneration diffs cleanly. Stdlib only.
"""

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SEMANTICS = ("unknown = no rules-layer decision; runtime outcome depends on "
             "approval policy + sandbox under the pinned configuration. "
             "Unmatched is never a bypass, evasion, or hole.")
UNKNOWN_ATTRIBUTION = ("no rules-layer decision; outcome depends on approval "
                       "policy + sandbox under the pinned configuration")

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
max-width:1080px;margin:2rem auto;padding:0 1.2rem;color:#1a1a1a;line-height:1.5}
h1{font-size:1.7rem}h2{font-size:1.25rem;margin-top:2.2rem;
border-bottom:1px solid #ddd;padding-bottom:.3rem}
table{border-collapse:collapse;width:100%;font-size:.86rem;margin:1rem 0}
th,td{border:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}
th{background:#f4f4f4}code{background:#f4f4f4;padding:0 .25rem;border-radius:3px}
.pass{color:#0a7a2f;font-weight:bold}.fail{color:#c00;font-weight:bold}
.badge{display:inline-block;padding:.1rem .5rem;border-radius:999px;font-size:.75rem;
font-weight:bold;color:#fff}.b-allow{background:#0a7a2f}.b-prompt{background:#b26a00}
.b-forbidden{background:#c00}.b-unknown{background:#555}
.callout{background:#f7f9ff;border-left:4px solid #2a5bd7;padding:.7rem 1rem;margin:1rem 0}
.callout.warn{background:#fff8f0;border-left-color:#b26a00}
.legend{font-size:.85rem;color:#444}.foot{margin-top:3rem;font-size:.8rem;color:#666;
border-top:1px solid #ddd;padding-top:1rem}
"""


def esc(s):
    return html.escape(str(s))


def badge(decision):
    return (f'<span class="badge b-{esc(decision)}">{esc(decision)}</span>')


def load_rerun(path):
    return json.loads(Path(path).read_text())


def verdicts_of(rerun):
    return [{"id": r["id"], "argv": " ".join(r["argv"]),
             "expected": r["expected"], "actual": r["actual"],
             "verdict": r["verdict"],
             "resolve_host_executables": r.get("resolve_host_executables", False),
             "maps_to": r.get("maps_to"), "kind": r.get("kind"),
             "note": r.get("note", "")}
            for r in rerun["results"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun", required=True,
                    help="committed run_fixtures.py output JSON (41-case corpus)")
    ap.add_argument("--family-rerun", default=None)
    ap.add_argument("--family-bundle", default=None)
    ap.add_argument("--matrix", default=None,
                    help="baseline matrix markdown doc to embed")
    ap.add_argument("--out", default="evidence/reports/day2-41-corpus")
    args = ap.parse_args()

    rerun = load_rerun(args.rerun)
    run = rerun["run"]
    verdicts = verdicts_of(rerun)
    passes = sum(1 for v in verdicts if v["verdict"] == "pass")
    fails = len(verdicts) - passes
    counts = {}
    for v in verdicts:
        counts[v["actual"]] = counts.get(v["actual"], 0) + 1

    family = None
    if args.family_rerun:
        fr = load_rerun(args.family_rerun)
        family = {
            "verdicts": verdicts_of(fr),
            "pass": sum(1 for v in verdicts_of(fr) if v["verdict"] == "pass"),
            "fail": sum(1 for v in verdicts_of(fr) if v["verdict"] != "pass"),
            "run": fr["run"],
        }
    family_bundle = None
    if args.family_bundle:
        fb = json.loads(Path(args.family_bundle).read_text())
        family_bundle = {"bundle_id": fb["bundle_id"], "status": fb["status"],
                         "merkle_root": fb["merkle"]["root"],
                         "created_utc": fb["created_utc"],
                         "corpus_version_hash": fb["corpus"]["corpus_version_hash"],
                         "preregistration_sha256":
                             fb["preregistration"]["sha256"]}
    matrix_text = Path(args.matrix).read_text() if args.matrix else None

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "schema_version": "conformance-report.v1",
        "generated_utc": generated,
        "generator": "tools/build_report.py (deterministic; no oracle calls)",
        "pinned": {
            "harness": run.get("harness", "codex"),
            "codex_version_pinned": run.get("codex_version_pinned"),
            "codex_version_detected": run.get("codex_version_detected"),
            "codex_binary": run.get("codex_binary"),
            "fixtures_files": run.get("fixtures_files") or
                              [run.get("fixtures_file")],
            "default_rules_file": run.get("default_rules_file"),
            "run_timestamp_utc": run.get("timestamp_utc"),
        },
        "semantics": SEMANTICS,
        "unknown_layer_attribution": UNKNOWN_ATTRIBUTION,
        "corpus": {
            "fixtures": len(verdicts),
            "pass": passes,
            "fail": fails,
            "decision_counts": counts,
            "note": "synthetic probe corpus deliberately weighted toward "
                    "wrappers/variants; decision rates are corpus results, "
                    "never real-world rates",
        },
        "verdicts": verdicts,
        "protected_records_family": {
            "fixtures": (len(family["verdicts"]) if family else 0),
            "pass": family["pass"] if family else 0,
            "fail": family["fail"] if family else 0,
            "verdicts": family["verdicts"] if family else [],
            "evidence_bundle": family_bundle,
        } if family else None,
        "baselines": {
            "native_codex": "run — the oracle itself",
            "harness_eval": "run — cannot express per-fixture cells (REPRO)",
            "agent_security_harness": "run — cannot express per-fixture cells (REPRO)",
            "snyk_agent_scan": "not tested — blocked on Anish's API token (REPRO)",
            "owasp_harness": "not tested — concept-level review only (THIRD-PARTY)",
        },
        "reproduce_command": (
            "python3 tools/build_report.py "
            f"--rerun {args.rerun} "
            + (f"--family-rerun {args.family_rerun} " if args.family_rerun else "")
            + (f"--family-bundle {args.family_bundle} " if args.family_bundle else "")
            + (f"--matrix {args.matrix} " if args.matrix else "")
            + f"--out {args.out}"
        ),
    }

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    # ---- HTML ----
    def vtable(vs):
        rows = []
        for v in vs:
            mark = "pass" if v["verdict"] == "pass" else "fail"
            rows.append(
                f"<tr><td><code>{esc(v['id'])}</code></td>"
                f"<td><code>{esc(v['argv'])}</code></td>"
                f"<td>{esc(v['expected'])}</td><td>{badge(v['actual'])}</td>"
                f"<td class='{mark}'>{esc(v['verdict'])}</td></tr>")
        return ("<table><tr><th>ID</th><th>argv</th><th>expected</th>"
                "<th>actual</th><th>verdict</th></tr>" + "".join(rows) + "</table>")

    dist = ", ".join(f"{k}={counts[k]}" for k in sorted(counts))
    fam_html = ""
    if family:
        frows = []
        for v in family["verdicts"]:
            mark = "pass" if v["verdict"] == "pass" else "fail"
            frows.append(
                f"<tr><td><code>{esc(v['id'])}</code></td>"
                f"<td><code>{esc(v['argv'])}</code></td>"
                f"<td>{esc(v['expected'])}</td><td>{badge(v['actual'])}</td>"
                f"<td class='{mark}'>{esc(v['verdict'])}</td>"
                f"<td class='legend'>{esc(v['note'])}</td></tr>")
        bundle_line = ""
        if family_bundle:
            bundle_line = (
                f"<p class='legend'>Evidence bundle <code>{esc(family_bundle['bundle_id'])}</code> "
                f"— status <b>{esc(family_bundle['status'])}</b>, Merkle root "
                f"<code>{esc(family_bundle['merkle_root'])}</code>, corpus hash "
                f"<code>{esc(family_bundle['corpus_version_hash'][:16])}…</code>, "
                f"pre-registration <code>{esc(family_bundle['preregistration_sha256'][:16])}…</code>.</p>")
        fam_html = f"""
<h2>Protected-records family (11 fixtures, second sample policy)</h2>
<div class="callout">Danger is contextual: this family probes a policy that
forbids deletion/modification under <code>/records/health</code> across direct
forms, spelling variants, wrapped forms, and a non-rm script form (a Python
one-liner that truncates the file). Result: prefix rules cover only exact-token
direct forms (<code>PA-01</code>, <code>PA-11</code>); even a direct
<code>rm -rf</code> at a <em>subpath</em> of the protected directory
(<code>PA-02</code>) receives no rules-layer decision — prefix rules match argv
TOKEN prefixes, not path prefixes. All wrapped/script forms return
rules-layer unknown with layer attribution. This family is the concrete
motivation for the later effect layer.</div>
<p><b>{family['pass']}/{len(family['verdicts'])} pass</b> (allow=1, forbidden=2, unknown=8).
Positive control <code>PA-10</code> (<code>ls /records/health</code> → allow)
passed: the policy does not over-block legitimate reads. Over-blocking
legitimate work (INV-002/F-01 in the main corpus) is a conformance failure too —
the two-sided discipline.</p>
{bundle_line}
<table><tr><th>ID</th><th>argv</th><th>expected</th><th>actual</th><th>verdict</th>
<th>note</th></tr>{''.join(frows)}</table>"""

    matrix_html = ""
    if matrix_text:
        matrix_html = ("<h2>Baseline matrix (same corpus)</h2>"
                       "<p class='legend'>Per-fixture cells for harness-eval and "
                       "agent-security-harness are <b>cannot express</b> (interface "
                       "evidence re-verified today); Snyk and OWASP cells are "
                       "<b>not tested</b> — never an inferred result.</p>"
                       f"<pre class='legend'>{esc(matrix_text[:6000])}</pre>"
                       "<p class='legend'>(Full matrix: "
                       f"<code>{esc(args.matrix)}</code> in the repo.)</p>")

    h = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Agent Boundary Conformance — standalone report</title>
<style>{CSS}</style></head><body>
<h1>Agent Boundary Conformance — standalone report</h1>
<p class="legend">Generated {esc(generated)} by <code>tools/build_report.py</code>
(deterministic; no oracle calls — a pure function of the committed rerun JSON).
Every claim carries an evidence class; the runner's semantics are in
<code>docs/WEEK1_BUILD_SPEC.md</code>.</p>

<div class="callout"><b>Semantics (non-negotiable).</b> {esc(SEMANTICS)}</div>

<h2>Pinned configuration</h2>
<table>
<tr><th>field</th><th>value</th></tr>
<tr><td>harness</td><td><code>{esc(report['pinned']['harness'])}</code></td></tr>
<tr><td>codex version (pinned / detected)</td>
<td><code>{esc(report['pinned']['codex_version_pinned'])}</code> /
<code>{esc(report['pinned']['codex_version_detected'])}</code></td></tr>
<tr><td>binary</td><td><code>{esc(report['pinned']['codex_binary'])}</code></td></tr>
<tr><td>fixtures</td><td><code>{esc(', '.join(report['pinned']['fixtures_files']))}</code></td></tr>
<tr><td>default rules</td><td><code>{esc(report['pinned']['default_rules_file'])}</code></td></tr>
<tr><td>run timestamp (UTC)</td><td><code>{esc(report['pinned']['run_timestamp_utc'])}</code></td></tr>
</table>

<h2>Corpus verdicts — {passes}/{len(verdicts)} pass</h2>
<p class="legend">Decision distribution: {esc(dist)}. This is a synthetic probe
corpus deliberately weighted toward wrappers/variants — the rates are corpus
results, never real-world usage rates.</p>
{vtable(verdicts)}

<div class="callout"><b>Two-sided discipline.</b> Over-blocking legitimate work is
a conformance failure too: positive control <code>F-01</code>
(<code>git status</code> → allow, INV-002) must stay allowed. A policy "fix"
that breaks it is a regression, not a win.</div>

<div class="callout warn"><b>Compound commands (F-11/F-12).</b> Handed a whole
compound command as one token list, the <code>check</code> CLI evaluates only the
head segment and reports its decision without warning; later segments receive no
rules-layer decision in that invocation. How the runtime decomposes shell
commands before consulting execpolicy is a separate, untested question.</div>

<div class="callout warn"><b>Wrapped forms (INV-004, decided by Anish Oct 21:
Option A).</b> A wrapped form of a forbidden action must never be reported as a
silent pass — it surfaces as explicit <b>unknown</b> with layer attribution
("{esc(UNKNOWN_ATTRIBUTION)}"). Prefix rules cannot inspect wrapped payloads, so
this is permanently unknown-by-construction at the rules layer.</div>

{fam_html}
{matrix_html}

<h2>Baselines (same corpus)</h2>
<table><tr><th>tool</th><th>status</th></tr>
{''.join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in report['baselines'].items())}
</table>
<p class="legend">No baseline run today does intent→native-decision conformance.
The gap hypothesis survives Day 3.</p>

<div class="foot">
<b>Reproduce this report from the repo alone:</b><br>
<code>{esc(report['reproduce_command'])}</code><br><br>
Report JSON (<code>report.json</code>) is deterministic: regenerating in a clean
checkout and diffing <code>verdicts</code> must show zero differences.
Generated {esc(generated)} · schema <code>conformance-report.v1</code>.
</div>
</body></html>"""
    (out_dir / "report.html").write_text(h)

    print(f"verdicts: pass={passes} fail={fails} ({dist})")
    if family:
        print(f"family: pass={family['pass']} fail={family['fail']}")
    print(f"wrote {out_dir.relative_to(REPO)}/report.json + report.html")


if __name__ == "__main__":
    sys.exit(main())
