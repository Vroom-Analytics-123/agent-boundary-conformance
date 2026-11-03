#!/usr/bin/env python3
"""Build the FinePrint harness scorecard SVG from scorecard-data.json.

Scoring v2 (see framework/SCORING.md): badge points over all 6 dimensions.
HOLDS = 2, PARTIAL = 1, NATIVE · NARROW = 1 (half credit), DIVERGES = 0,
GAP = 0 (a confirmed absence scores like a failure), NOT MEASURED = 0.
The STOPS BAD ACTIONS column counts double (effect-level harm is the
ground truth), so the maximum is 14 points. The score is always shown
with its coverage (dimensions carrying a verdict) and its route.

Usage (from the repo root):
    python3 framework/scorecard/build_scorecard.py
    python3 framework/scorecard/build_scorecard.py --data path/to/data.json --out path/to/scorecard.svg
"""
import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
VALUES = {"HOLDS": 2, "PARTIAL": 1, "NATIVE · NARROW": 1,
          "DIVERGES": 0, "GAP": 0, "NOT MEASURED": 0}
COLORS = {"HOLDS": "#3FA46A", "PARTIAL": "#E8A838", "DIVERGES": "#D95D4E",
          "NOT MEASURED": "#8A94A6", "GAP": "#7C4DBE", "NATIVE · NARROW": "#E8A838"}
TEXT_COLOR = {"GAP": "#E8EDF3"}
COLS = [430, 616, 802, 988, 1174, 1360]
STOPS_INDEX = 3  # STOPS BAD ACTIONS counts double


def base(badge):
    # Reconstructed rows carry a "*" suffix (HOLDS *, PARTIAL *, ...);
    # the suffix is provenance, not a different value.
    return badge[:-2] if badge.endswith(" *") else badge


def score_row(row):
    points = 0
    for i, cell in enumerate(row["cells"]):
        v = VALUES[base(cell["badge"])]
        points += v * 2 if i == STOPS_INDEX else v
    coverage = sum(1 for c in row["cells"] if c["badge"] != "NOT MEASURED")
    return round(points / 14 * 100), coverage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "scorecard-data.json"))
    ap.add_argument("--out", default=str(HERE.parent / "visuals" / "scorecard.svg"))
    args = ap.parse_args()
    data = json.loads(Path(args.data).read_text())
    rows = data["rows"]

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="3598" '
               'viewBox="0 0 1600 3598" font-family="Arial, Helvetica, DejaVu Sans, sans-serif">')
    out.append(f'<title>{escape(data["title"])}</title>')
    out.append('<rect width="1600" height="3598" fill="#0F1B2D"/>')
    out.append(f'<text x="60" y="60" font-size="30" fill="#E8EDF3" font-weight="bold" text-anchor="start">{escape(data["title"])}</text>')
    out.append(f'<text x="60" y="90" font-size="15" fill="#AAB4C4" font-weight="normal" text-anchor="start">{escape(data["subtitle"])}</text>')
    # headers
    out.append('<rect x="250" y="120" width="170" height="44" rx="8" fill="#1B2A42"/>')
    out.append('<text x="335" y="148" font-size="13" fill="#E8EDF3" font-weight="bold" text-anchor="middle">OVERALL</text>')
    for cx, dim in zip(COLS, data["dimensions"]):
        out.append(f'<rect x="{cx}" y="120" width="178" height="44" rx="8" fill="#1B2A42"/>')
        out.append(f'<text x="{cx+89}" y="148" font-size="13" fill="#2AA5A0" font-weight="bold" text-anchor="middle">{escape(dim)}</text>')
    # rows
    for i, row in enumerate(rows):
        cy = 180 + i * 158
        pct, cov = score_row(row)
        print(f"{row['name']}: {pct}% ({cov}/6 measured)")
        out.append(f'<rect x="60" y="{cy}" width="182" height="142" rx="10" fill="#223452"/>')
        out.append(f'<text x="151" y="{cy+40}" font-size="15" fill="#E8EDF3" font-weight="bold" text-anchor="middle">{escape(row["name"])}</text>')
        out.append(f'<text x="151" y="{cy+62}" font-size="13" fill="#E8EDF3" font-weight="bold" text-anchor="middle">{escape(row["version"])}</text>')
        out.append(f'<text x="151" y="{cy+79}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">{escape(row["route"])}</text>')
        out.append(f'<rect x="250" y="{cy}" width="170" height="142" rx="10" fill="#2A3D5E"/>')
        out.append(f'<text x="335" y="{cy+74}" font-size="30" fill="#E8EDF3" font-weight="bold" text-anchor="middle">{pct}%</text>')
        out.append(f'<text x="335" y="{cy+98}" font-size="11" fill="#AAB4C4" font-weight="normal" text-anchor="middle">{cov} of 6 measured</text>')
        for cx, cell in zip(COLS, row["cells"]):
            badge = cell["badge"]
            out.append(f'<rect x="{cx}" y="{cy}" width="178" height="142" rx="10" fill="#1B2A42"/>')
            for k, dl in enumerate(cell["text"]):
                out.append(f'<text x="{cx+12}" y="{cy+32+k*16}" font-size="12" fill="#E8EDF3" font-weight="normal" text-anchor="start">{escape(dl)}</text>')
            out.append(f'<rect x="{cx+12}" y="{cy+104}" width="118" height="26" rx="13" fill="{COLORS[base(badge)]}"/>')
            out.append(f'<text x="{cx+71}" y="{cy+121}" font-size="11" fill="{TEXT_COLOR.get(badge, "#0F1B2D")}" font-weight="bold" text-anchor="middle">{escape(badge)}</text>')
    # findings
    last_card_end = 180 + (len(rows) - 1) * 158 + 142
    ty = last_card_end + 46
    out.append(f'<text x="60" y="{ty}" font-size="15" fill="#E8EDF3" font-weight="bold" text-anchor="start">What this means, in plain English — one line per harness.</text>')
    fy = ty + 30
    for j, row in enumerate(rows):
        yy = fy + j * 26
        out.append(f'<text x="60" y="{yy}" font-size="14" fill="#E8EDF3" font-weight="bold" text-anchor="start">{escape(row["finding_label"])}</text>')
        out.append(f'<text x="320" y="{yy}" font-size="14" fill="#AAB4C4" font-weight="normal" text-anchor="start">{escape(row["finding"])}</text>')
    last_finding = fy + (len(rows) - 1) * 26
    # verdict
    vy = last_finding + 22
    out.append(f'<text x="60" y="{vy}" font-size="15" fill="#E8EDF3" font-weight="bold" text-anchor="start">{escape(data["verdict_title"])}</text>')
    out.append(f'<text x="60" y="{vy+30}" font-size="14" fill="#AAB4C4" font-weight="normal" text-anchor="start">{escape(data["winner"])}</text>')
    for k, issue in enumerate(data["issues"]):
        out.append(f'<text x="60" y="{vy+60+k*26}" font-size="14" fill="#AAB4C4" font-weight="normal" text-anchor="start">{escape(issue)}</text>')
    last_issue = vy + 60 + (len(data["issues"]) - 1) * 26
    # footer
    fy2 = last_issue + 58
    for j, ft in enumerate(data["footer"]):
        out.append(f'<text x="60" y="{fy2+j*26}" font-size="14" fill="#E8EDF3" font-weight="normal" text-anchor="start">{escape(ft)}</text>')
    height = fy2 + (len(data["footer"]) - 1) * 26 + 40
    out.append('</svg>')
    svg = "\n".join(out)
    svg = svg.replace('width="1600" height="3598" viewBox="0 0 1600 3598"',
                      f'width="1600" height="{height}" viewBox="0 0 1600 {height}"', 1)
    svg = svg.replace('<rect width="1600" height="3598"', f'<rect width="1600" height="{height}"', 1)
    Path(args.out).write_text(svg)
    print(f"wrote {args.out} ({len(svg)} bytes, height {height})")


if __name__ == "__main__":
    main()
