#!/usr/bin/env python3
"""Top-scorers visual for scorecard v4 (PROVISIONAL, UNSEALED).

Reads framework/scorecard/v4-scorecard-data.json (computed by
tools/build_v4_scorecard.py) and renders framework/scorecard/top-scorers-v4.svg.
Row order and groupings are presentation choices; every NUMBER comes from the
data file except the historical 'Amp was 12.87' annotation, which is git
history (decision-only basis, superseded by the live row).
Bars show D + A + E stacked on a 0-100 point scale; /75 rows show their total
on the same scale, tagged '(of 75)' — never silently scaled to 100.
Palette matches the repo visual polish (dark navy).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "framework", "scorecard", "v4-scorecard-data.json")
OUT = os.path.join(ROOT, "framework", "scorecard", "top-scorers-v4.svg")

BG, PANEL, CARD = "#0F1B2D", "#1B2A42", "#223452"
TEXT, MUTED, BORDER = "#E8EDF3", "#AAB4C4", "#8A94A6"
TEAL, AMBER, GREEN = "#2AA5A0", "#E8A838", "#3FA46A"

W, BAR_X, BAR_W = 1200, 40, 640
SCALE = BAR_W / 100.0


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def segs(d, a, e):
    """Stacked D/A/E segments; a=None renders a hatched N/A block."""
    x, out = BAR_X, []
    for val, color in ((d, TEAL), (a, AMBER), (e, GREEN)):
        if val is None:
            continue
        w = val * SCALE
        if w >= 1:
            out.append(f'<rect x="{x:.1f}" y="{{y}}" width="{w:.1f}" height="22" fill="{color}"/>')
            if w >= 34:
                out.append(f'<text x="{x + w / 2:.1f}" y="{{y2}}" text-anchor="middle" font-size="12" fill="#0F1B2D" font-weight="bold">{val:.2f}</text>')
        x += w
    return out, x


def main():
    rows = {r["harness"]: r for r in json.load(open(DATA))["rows"]}
    full = ["Amp", "OpenClaw", "Claude Code (live)", "Hermes Agent", "Omnigent"]
    of75 = ["Gemini CLI", "Copilot CLI"]
    rest = ["OpenCode", "Goose", "Strands Agents", "LangGraph", "CrewAI"]
    dec_only = ["Claude Code", "Codex", "Cursor", "Pi"]

    y, parts = 0, []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="900" viewBox="0 0 {W} 900" font-family="Inter, DejaVu Sans, sans-serif">')
    parts.append(f'<rect width="{W}" height="900" fill="{BG}"/>')
    parts.append(f'<text x="40" y="52" font-size="30" font-weight="bold" fill="{TEXT}">Top scorers — Scorecard v4, live basis</text>')
    parts.append(f'<text x="40" y="84" font-size="15" fill="{MUTED}">PROVISIONAL · UNSEALED · Higher = stronger hold rate — NOT a security grade</text>')
    parts.append(f'<rect x="40" y="100" width="14" height="14" fill="{TEAL}"/><text x="60" y="112" font-size="14" fill="{TEXT}">Decision / 25</text>')
    parts.append(f'<rect x="190" y="100" width="14" height="14" fill="{AMBER}"/><text x="210" y="112" font-size="14" fill="{TEXT}">Approval / 25</text>')
    parts.append(f'<rect x="340" y="100" width="14" height="14" fill="{GREEN}"/><text x="360" y="112" font-size="14" fill="{TEXT}">Effect / 50</text>')
    y = 140

    def row(name, tag, cov):
        nonlocal y
        r = rows[name]
        total = r["D"] + (r["A"] or 0) + r["E"]
        parts.append(f'<text x="40" y="{y + 20}" font-size="20" font-weight="bold" fill="{TEXT}">{esc(name)}</text>')
        parts.append(f'<text x="1160" y="{y + 20}" font-size="22" font-weight="bold" fill="{TEXT}" text-anchor="end">{total:.2f}{tag}</text>')
        parts.append(f'<rect x="{BAR_X}" y="{y + 30}" width="{BAR_W}" height="22" fill="{CARD}" stroke="{BORDER}" stroke-width="1"/>')
        seg, _ = segs(r["D"], r["A"], r["E"])
        for s in seg:
            parts.append(s.format(y=y + 30, y2=y + 46))
        if r["A"] is None:
            parts.append(f'<text x="{BAR_X + BAR_W + 14}" y="{y + 46}" font-size="14" fill="{MUTED}">approval N/A · {cov}</text>')
        else:
            parts.append(f'<text x="{BAR_X + BAR_W + 14}" y="{y + 46}" font-size="14" fill="{MUTED}">{cov}</text>')
        y += 66

    for n in full:
        r = rows[n]
        row(n, "", f"live · D {r['d_cov']} · E {r['e_cov']} · A {r['a_cov']}")
    parts.append(f'<line x1="40" y1="{y + 4}" x2="1160" y2="{y + 4}" stroke="{BORDER}" stroke-width="1"/>')
    parts.append(f'<text x="40" y="{y + 30}" font-size="15" font-weight="bold" fill="{AMBER}">Out of 75 — approval N/A (headless modes preclude dialogs)</text>')
    y += 44
    for n in of75:
        r = rows[n]
        row(n, " (of 75)", f"live · D {r['d_cov']} · E {r['e_cov']}")
    rest_txt = " · ".join(f"{n} {rows[n]['D'] + rows[n]['E']:.2f}" for n in rest)
    parts.append(f'<text x="40" y="{y + 22}" font-size="14" fill="{MUTED}">Also live: {esc(rest_txt)}</text>')
    y += 44
    parts.append(f'<line x1="40" y1="{y + 4}" x2="1160" y2="{y + 4}" stroke="{BORDER}" stroke-width="1"/>')
    parts.append(f'<text x="40" y="{y + 30}" font-size="15" font-weight="bold" fill="{MUTED}">Decision-only — NOT ranked against live rows</text>')
    dec_txt = " · ".join(f"{n} {rows[n]['total']:.2f}" for n in dec_only)
    parts.append(f'<text x="40" y="{y + 54}" font-size="14" fill="{MUTED}">Paper / oracle: {esc(dec_txt)} (Amp was 12.87 here — now live above)</text>')
    y += 84
    parts.append(f'<text x="40" y="{y + 10}" font-size="13" fill="{MUTED}">Coverage + route travel with every number. Computed by tools/build_v4_scorecard.py from v4-cells.json — never hand-set.</text>')
    parts.append('</svg>')
    svg = "\n".join(parts)
    # fix height to content
    svg = svg.replace('height="900" viewBox="0 0 1200 900', f'height="{y + 30}" viewBox="0 0 1200 {y + 30}')
    svg = svg.replace(f'<rect width="{W}" height="900" fill="{BG}"/>', f'<rect width="{W}" height="{y + 30}" fill="{BG}"/>')
    open(OUT, "w").write(svg + "\n")
    print(f"wrote {OUT} height={y + 30}")


if __name__ == "__main__":
    main()
