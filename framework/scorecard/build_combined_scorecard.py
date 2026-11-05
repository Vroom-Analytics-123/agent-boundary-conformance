#!/usr/bin/env python3
"""Build the COMBINED FinePrint harness scorecard SVG in the v2 card layout.

PROVISIONAL combined view — it does NOT promote v4 to the live badges and
does NOT change the live-scorecard status. The v2 grid data file
(framework/scorecard/scorecard-data.json) is left untouched, so the old v2
grid remains reproducible via framework/scorecard/build_scorecard.py.

Numbers: read ONLY from framework/scorecard/v4-scorecard-data.json (itself
computed by tools/build_v4_scorecard.py from v4-cells.json — never hand-set).
This generator formats those numbers; it invents none. Rerunning it against
the same data file produces byte-identical output.

Encoding (documented, not silent):
- Totals marked approval N/A are out of 75 (Decision + Effect only) and are
  NEVER rescaled to /100. The OVERALL cell shows "(of 75)".
- Rows are grouped by basis, never ranked across bases: live out-of-100
  rows, then live out-of-75 rows, then decision-only rows (NOT ranked
  against live rows). Within a group, rows sort by total descending
  (ties broken by name, so output is deterministic).
- The 'Gemini CLI (paper)' comparison row is excluded, like the v4 page's
  live table (it is a comparison basis, not a harness row).
- Findings lines carry NO numbers (qualitative only), so they cannot drift
  from the data file. Any number in the verdict section is formatted from
  the data file at build time.

Layout: the v2 card language (1600-wide dark navy canvas, name card,
OVERALL card, value cells, findings section, verdict section, footer).

Color language: the old v2 verdict-pill colors return as layer, basis, and
coverage cues — Decision teal, Approval amber, Effect green; live basis green,
of-75 amber, decision-only grey; full coverage green, partial amber, zero grey.
Colors encode layer, basis, and coverage only — never a grade. The old
DIVERGES red and GAP purple are deliberately unused (no failure verdict exists
in v4 layer numbers).

Usage (from the repo root):
    python3 framework/scorecard/build_combined_scorecard.py
    python3 framework/scorecard/build_combined_scorecard.py --data path/to/v4-scorecard-data.json --out path/to/scorecard.svg
"""
import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
BG, PANEL, CARD, OVERALL = "#0F1B2D", "#1B2A42", "#223452", "#2A3D5E"
TEXT, MUTED, BORDER = "#E8EDF3", "#AAB4C4", "#8A94A6"
TEAL, AMBER, GREEN = "#2AA5A0", "#E8A838", "#3FA46A"
# Color language (old v2 verdict-pill language, reused without grade semantics):
# layer numbers: Decision teal, Approval amber, Effect green (as in top-scorers-v4).
# Basis: live green, live-of-75 amber, decision-only grey. Coverage: full green,
# partial amber, zero grey. Red (#D95D4E) and purple (#7C4DBE) from the old
# DIVERGES/GAP pills are deliberately NOT reused — v4 layer numbers carry no
# failure-grade verdict, and red would invent one.
LAYER_COL = {"D": "#2AA5A0", "A": "#E8A838", "E": "#3FA46A"}
BASIS_COL = {"live": "#3FA46A", "live · of 75": "#E8A838", "decision-only": "#8A94A6"}
GROUP_RULE = {"full": "#3FA46A", "of75": "#E8A838", "dec": "#8A94A6"}


def cov_col(frac):
    """Coverage cue color for an 'x/24' or 'x/20' fraction string."""
    try:
        x, n = frac.split("/")
        x, n = int(x), int(n)
    except ValueError:
        return "#AAB4C4"
    if x == 0:
        return "#AAB4C4"
    return "#3FA46A" if x == n else "#E8A838"

NAME_X, OVERALL_X = 60, 250
COL_X = {"D": 430, "A": 616, "E": 802, "COV": 988}
COL_W = {"D": 178, "A": 178, "E": 178, "COV": 550}

# Qualitative findings only — no numbers, so nothing can drift from data.
FINDINGS = {
    "Amp": "Leads live, but credential reads execute — the hole.",
    "OpenClaw": "Stops everything attempted; overblocks benign work.",
    "Claude Code (live)": "Wrapper-aware deletions hold; exfiltration held by refusal; credential hole.",
    "Muse Code": "Approver denies, but credential content escapes via the read tool.",
    "Hermes Agent": "Stops all deletions; gaps execute elsewhere.",
    "Omnigent": "CEL denies hold deletions; exfiltration and credentials execute.",
    "Gemini CLI": "Policy covers rm only; exfiltration, credentials, deploy mostly execute.",
    "Codex": "Router forbids every deletion, yet deletions still execute via unlink.",
    "Copilot CLI": "Deploy proceeds without approval; rm denied, deletion routed around.",
    "OpenCode": "Default profile allows all bash; only benign passes.",
    "Goose": "Default profile allows all; only benign passes.",
    "Strands Agents": "No policy, no approval; only benign passes.",
    "LangGraph": "No policy, no approval; only benign passes.",
    "CrewAI": "No policy, no approval; only benign passes.",
    "Claude Code": "Paper adapter; decision only, no live v1 run.",
    "Cursor": "Paper adapter; decision only, no live v1 run.",
    "Pi": "No permission system by design.",
}


def total_of(row):
    """Display total: stored total, or D+E for approval-N/A rows (never rescaled)."""
    if row["total"] is not None:
        return row["total"], False
    return round(row["D"] + row["E"], 2), True


def group_of(row):
    if row["e_cov"] == "0/24":
        return "dec"
    if row["A"] is None:
        return "of75"
    return "full"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "v4-scorecard-data.json"))
    ap.add_argument("--out", default=str(HERE.parent / "visuals" / "scorecard.svg"))
    args = ap.parse_args()
    data = json.loads(Path(args.data).read_text())
    rows = [r for r in data["rows"] if r["harness"] != "Gemini CLI (paper)"]
    for r in rows:
        assert r["harness"] in FINDINGS, f"no finding prose for {r['harness']}"
    full = sorted([r for r in rows if group_of(r) == "full"],
                  key=lambda r: (-r["total"], r["harness"]))
    of75 = sorted([r for r in rows if group_of(r) == "of75"],
                  key=lambda r: (-(r["D"] + r["E"]), r["harness"]))
    dec = sorted([r for r in rows if group_of(r) == "dec"],
                 key=lambda r: (-r["total"], r["harness"]))
    groups = [("Live basis — totals out of 100", full),
              ("Live basis — approval N/A, totals out of 75 (never rescaled to 100)", of75),
              ("Decision-only — NOT ranked against live rows", dec)]
    amp_total = next(r["total"] for r in rows if r["harness"] == "Amp")

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="3598" '
               'viewBox="0 0 1600 3598" font-family="Arial, Helvetica, DejaVu Sans, sans-serif">')
    out.append('<rect width="1600" height="3598" fill="#0F1B2D"/>')
    out.append('<text x="60" y="60" font-size="30" fill="#E8EDF3" font-weight="bold" text-anchor="start">FinePrint harness scorecard — combined live-basis view (PROVISIONAL)</text>')
    out.append('<text x="60" y="90" font-size="15" fill="#AAB4C4" font-weight="normal" text-anchor="start">v4 layer totals (Decision /25 · Approval /25 · Effect /50) in the v2 card layout · 16 harnesses, 17 rows (Claude Code has live + decision-only rows) · Nov 4, 2026 live series · Higher = stronger hold rate — NOT a security grade</text>')
    out.append('<rect x="60" y="104" width="1480" height="4" fill="#2AA5A0"/>')
    out.append('<rect x="250" y="120" width="170" height="44" rx="8" fill="#1B2A42"/>')
    out.append('<text x="335" y="148" font-size="13" fill="#E8EDF3" font-weight="bold" text-anchor="middle">OVERALL</text>')
    headers = [("D", "DECISION /25"), ("A", "APPROVAL /25"), ("E", "EFFECT /50"), ("COV", "COVERAGE")]
    for key, label in headers:
        cx, w = COL_X[key], COL_W[key]
        out.append(f'<rect x="{cx}" y="120" width="{w}" height="44" rx="8" fill="#1B2A42"/>')
        out.append(f'<text x="{cx + w // 2}" y="148" font-size="13" fill="#2AA5A0" font-weight="bold" text-anchor="middle">{label}</text>')

    y = 180
    for label, grows in groups:
        gkey = "full" if label.startswith("Live basis — totals out of 100") else ("of75" if "approval N/A" in label else "dec")
        out.append(f'<text x="60" y="{y + 20}" font-size="15" fill="{GROUP_RULE[gkey]}" font-weight="bold" text-anchor="start">{escape(label)}</text>')
        out.append(f'<rect x="60" y="{y + 28}" width="1480" height="2" fill="{GROUP_RULE[gkey]}"/>')
        y += 34
        for row in grows:
            cy = y
            total, is75 = total_of(row)
            basis = {"full": "live", "of75": "live · of 75", "dec": "decision-only"}[group_of(row)]
            if group_of(row) == "dec" and row["harness"] == "Pi":
                scen = "vendor-confirmed absence"
            elif group_of(row) == "dec":
                scen = "24 adapter scenarios"
            else:
                scen = "24 v1 scenarios"
            print(f"{row['harness']}: D={row['D']} A={row['A']} E={row['E']} total={total}{' (of 75)' if is75 else ''}")
            out.append(f'<rect x="60" y="{cy}" width="182" height="142" rx="10" fill="#223452"/>')
            out.append(f'<text x="151" y="{cy + 40}" font-size="15" fill="#E8EDF3" font-weight="bold" text-anchor="middle">{escape(row["harness"])}</text>')
            out.append(f'<text x="151" y="{cy + 62}" font-size="13" fill="{BASIS_COL[basis]}" font-weight="normal" text-anchor="middle">{escape(basis)}</text>')
            out.append(f'<text x="151" y="{cy + 79}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">{escape(scen)}</text>')
            out.append(f'<rect x="250" y="{cy}" width="170" height="142" rx="10" fill="#2A3D5E"/>')
            out.append(f'<text x="335" y="{cy + 74}" font-size="30" fill="{"#E8A838" if group_of(row) != "dec" else "#AAB4C4"}" font-weight="bold" text-anchor="middle">{total:.2f}</text>')
            out.append(f'<rect x="305" y="{cy + 82}" width="60" height="4" fill="{"#E8A838" if group_of(row) != "dec" else "#AAB4C4"}"/>')
            out.append(f'<text x="335" y="{cy + 98}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">{"(of 75)" if is75 else ("(decision-only)" if group_of(row) == "dec" else "(of 100)")}</text>')
            # Decision cell
            out.append(f'<rect x="{COL_X["D"]}" y="{cy}" width="178" height="142" rx="10" fill="#1B2A42"/>')
            out.append(f'<text x="{COL_X["D"] + 89}" y="{cy + 74}" font-size="26" fill="#2AA5A0" font-weight="bold" text-anchor="middle">{row["D"]:.2f}</text>')
            out.append(f'<rect x="{COL_X["D"] + 59}" y="{cy + 82}" width="60" height="4" fill="#2AA5A0"/>')
            out.append(f'<text x="{COL_X["D"] + 89}" y="{cy + 98}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">/ 25{" · no engine" if row["D"] == 0.0 and row["harness"] in ("Muse Code", "OpenClaw", "Hermes Agent", "Strands Agents", "LangGraph", "CrewAI") else ""}</text>')
            # Approval cell
            out.append(f'<rect x="{COL_X["A"]}" y="{cy}" width="178" height="142" rx="10" fill="#1B2A42"/>')
            if row["A"] is None:
                out.append(f'<text x="{COL_X["A"] + 89}" y="{cy + 74}" font-size="26" fill="#AAB4C4" font-weight="bold" text-anchor="middle">N/A</text>')
                out.append(f'<text x="{COL_X["A"] + 89}" y="{cy + 98}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">mode-precluded</text>')
            else:
                sub = {"not-observed": "not observed", "no-layer": "no layer"}.get(row["approval_status"], "")
                out.append(f'<text x="{COL_X["A"] + 89}" y="{cy + 74}" font-size="26" fill="#E8A838" font-weight="bold" text-anchor="middle">{row["A"]:.2f}</text>')
                out.append(f'<rect x="{COL_X["A"] + 59}" y="{cy + 82}" width="60" height="4" fill="#E8A838"/>')
                out.append(f'<text x="{COL_X["A"] + 89}" y="{cy + 98}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">/ 25{sub and " · " + sub or ""}</text>')
            # Effect cell
            out.append(f'<rect x="{COL_X["E"]}" y="{cy}" width="178" height="142" rx="10" fill="#1B2A42"/>')
            out.append(f'<text x="{COL_X["E"] + 89}" y="{cy + 74}" font-size="26" fill="#3FA46A" font-weight="bold" text-anchor="middle">{row["E"]:.2f}</text>')
            out.append(f'<rect x="{COL_X["E"] + 59}" y="{cy + 82}" width="60" height="4" fill="#3FA46A"/>')
            out.append(f'<text x="{COL_X["E"] + 89}" y="{cy + 98}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">/ 50</text>')
            # Coverage cell
            out.append(f'<rect x="{COL_X["COV"]}" y="{cy}" width="550" height="142" rx="10" fill="#1B2A42"/>')
            out.append(f'<text x="{COL_X["COV"] + 16}" y="{cy + 56}" font-size="14" font-weight="normal" text-anchor="start"><tspan fill="#E8EDF3">D </tspan><tspan fill="{cov_col(row["d_cov"])}">{row["d_cov"]}</tspan><tspan fill="#AAB4C4"> · </tspan><tspan fill="#E8EDF3">E </tspan><tspan fill="{cov_col(row["e_cov"])}">{row["e_cov"]}</tspan></text>')
            if row["A"] is None:
                cov2 = "approval N/A (mode precludes dialogs)"
            elif group_of(row) == "dec":
                cov2 = {"not-observed": "approval not observed", "no-layer": "approval: no layer"}.get(row["approval_status"], f"approval {row['a_cov']}")
            else:
                cov2 = f"approval {row['a_cov']}"
            if group_of(row) != "dec" and row["A"] is not None:
                out.append(f'<text x="{COL_X["COV"] + 16}" y="{cy + 82}" font-size="14" font-weight="normal" text-anchor="start"><tspan fill="#E8EDF3">approval </tspan><tspan fill="{cov_col(row["a_cov"])}">{row["a_cov"]}</tspan></text>')
            else:
                out.append(f'<text x="{COL_X["COV"] + 16}" y="{cy + 82}" font-size="14" fill="#AAB4C4" font-weight="normal" text-anchor="start">{escape(cov2)}</text>')
            y += 158
    # findings
    ty = y + 46
    out.append(f'<text x="60" y="{ty}" font-size="15" fill="#E8EDF3" font-weight="bold" text-anchor="start">What this means, in plain English — one line per harness.</text>')
    fy = ty + 30
    all_rows = full + of75 + dec
    for j, row in enumerate(all_rows):
        yy = fy + j * 26
        out.append(f'<rect x="44" y="{yy - 11}" width="10" height="10" fill="{GROUP_RULE[group_of(row)]}"/>')
        out.append(f'<text x="60" y="{yy}" font-size="14" fill="#E8EDF3" font-weight="bold" text-anchor="start">{escape(row["harness"])}:</text>')
        out.append(f'<text x="320" y="{yy}" font-size="14" fill="#AAB4C4" font-weight="normal" text-anchor="start">{escape(FINDINGS[row["harness"]])}</text>')
    last_finding = fy + (len(all_rows) - 1) * 26
    vy = last_finding + 22
    out.append(f'<text x="60" y="{vy}" font-size="15" fill="#E8EDF3" font-weight="bold" text-anchor="start">Verdict</text>')
    out.append(f'<text x="60" y="{vy + 30}" font-size="14" font-weight="normal" text-anchor="start"><tspan fill="#AAB4C4">Highest live total: Amp </tspan><tspan fill="#E8A838" font-weight="bold">{amp_total:.2f}</tspan><tspan fill="#AAB4C4"> — but on live evidence with a credential hole, not a clean win.</tspan></text>')
    issues = [
        "No harness wins cleanly on live evidence: every leader has a hole in some family.",
        "Decision and effect disagree where it matters: forbidding a command is not stopping its bypass.",
        "Approval is the thinnest layer: where dialogs cannot appear, totals are out of 75 and flagged, never rescaled.",
        "Pi ships no permission system by design; reference agents with no policy layer score on benign passes only.",
    ]
    for k, issue in enumerate(issues):
        out.append(f'<text x="60" y="{vy + 60 + k * 26}" font-size="14" fill="#AAB4C4" font-weight="normal" text-anchor="start">{escape(issue)}</text>')
    last_issue = vy + 60 + (len(issues) - 1) * 26
    fy2 = last_issue + 58
    footer = [
        "PROVISIONAL combined view: v4 layer totals in the v2 card layout. It does NOT promote v4 to the live badges;",
        "sealing alone moves no badge — promotion to the live scorecard still needs the owner's explicit word.",
        "Scenarios generated with Meta muse-spark-1.3 · Built with Muse AI.",
        "Method: framework/SCORING-v4.md · Full table: framework/scorecard/v4-scorecard.md · Bundles: evidence/live-2026-11-04/.",
        "Numbers computed by tools/build_v4_scorecard.py from v4-cells.json — never hand-set; /75 totals never rescaled to /100.",
    ]
    for j, ft in enumerate(footer):
        fcol = "#E8A838" if j == 0 else "#E8EDF3"
        fweight = "bold" if j == 0 else "normal"
        out.append(f'<text x="60" y="{fy2 + j * 26}" font-size="14" fill="{fcol}" font-weight="{fweight}" text-anchor="start">{escape(ft)}</text>')
    height = fy2 + (len(footer) - 1) * 26 + 40
    out.append('</svg>')
    svg = "\n".join(out)
    svg = svg.replace('width="1600" height="3598" viewBox="0 0 1600 3598"',
                      f'width="1600" height="{height}" viewBox="0 0 1600 {height}"', 1)
    svg = svg.replace('<rect width="1600" height="3598"', f'<rect width="1600" height="{height}"', 1)
    Path(args.out).write_text(svg)
    print(f"wrote {args.out} ({len(svg)} bytes, height {height})")


if __name__ == "__main__":
    main()
