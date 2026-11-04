#!/usr/bin/env python3
"""Build framework/visuals/measured-result.svg deterministically.

Reads the pre-fix and post-fix decision counts from the committed sealed
bundles (never hand-typed constants) and renders a before/after visual
for the README's "The measured result" section. Deterministic: a pure
function of the two bundles — no timestamps, no randomness, fixed layout.

Inputs (relative to the repo root):
  evidence/day6-2026-10-26/bundle.json     — pre-fix distribution
  evidence/postfix-2026-10-22/bundle.json  — post-fix distribution
Output:
  framework/visuals/measured-result.svg

Assertions (fail loudly, never silently render wrong numbers):
  each bundle status == "valid", each total == 41,
  pre  == allow 6 / prompt 4 / forbidden 9 / unknown 22,
  post == allow 6 / prompt 4 / forbidden 11 / unknown 20.
"""

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent

PRE_PATH = REPO / "evidence" / "day6-2026-10-26" / "bundle.json"
POST_PATH = REPO / "evidence" / "postfix-2026-10-22" / "bundle.json"
OUT = REPO / "framework" / "visuals" / "measured-result.svg"

ORDER = ["allow", "prompt", "forbidden", "unknown"]
COLORS = {
    "allow": "#3FA46A",
    "prompt": "#E8A838",
    "forbidden": "#B3402E",
    "unknown": "#5B7BA5",
}
EXPECTED_PRE = {"allow": 6, "prompt": 4, "forbidden": 9, "unknown": 22}
EXPECTED_POST = {"allow": 6, "prompt": 4, "forbidden": 11, "unknown": 20}

BG = "#0F1B2D"
CARD = "#1B2A42"
BORDER = "#223452"
TEXT = "#E8EDF3"
MUTED = "#AAB4C4"
TEAL = "#2AA5A0"

W, H = 1200, 640
COL_W = 520
COL_X = {"pre": 60, "post": 620}
BAR_MAX = 472
BAR_H = 20
ROW_H = 66
ROWS_TOP = 196


def load_counts(path):
    bundle = json.loads(path.read_text())
    assert bundle["status"] == "valid", f"{path}: bundle must be valid"
    counts = {}
    for f in bundle["findings"]:
        d = f["actual_decision"]
        assert d in COLORS, f"{path}: unexpected decision {d}"
        counts[d] = counts.get(d, 0) + 1
    return counts


def bar_row(x, y, label, count, delta):
    bar_w = BAR_MAX * count / 22
    color = COLORS[label]
    parts = [
        f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="20" '
        f'fill="{TEXT}">{escape(label)}</text>',
        f'<text x="{x + COL_W - 24}" y="{y}" font-family="sans-serif" font-size="22" '
        f'font-weight="bold" fill="{TEXT}" text-anchor="end">{count}</text>',
    ]
    if delta:
        parts.append(
            f'<text x="{x + COL_W - 76}" y="{y}" font-family="sans-serif" '
            f'font-size="18" fill="{MUTED}" text-anchor="end">{escape(delta)}</text>'
        )
    parts.append(
        f'<rect x="{x}" y="{y + 12}" width="{BAR_MAX}" height="{BAR_H}" '
        f'rx="4" fill="{BORDER}" />'
    )
    parts.append(
        f'<rect x="{x}" y="{y + 12}" width="{bar_w:.1f}" height="{BAR_H}" '
        f'rx="4" fill="{color}" />'
    )
    return "\n".join(parts)


def main():
    pre = load_counts(PRE_PATH)
    post = load_counts(POST_PATH)
    assert pre == EXPECTED_PRE, f"pre-fix counts changed: {pre}"
    assert post == EXPECTED_POST, f"post-fix counts changed: {post}"
    assert sum(pre.values()) == 41 and sum(post.values()) == 41

    deltas = {
        k: ("+2" if post[k] - pre[k] == 2 else
            ("-2" if post[k] - pre[k] == -2 else ""))
        for k in ORDER
    }

    els = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}" />',
        f'<text x="600" y="58" font-family="sans-serif" font-size="30" '
        f'font-weight="bold" fill="{TEXT}" text-anchor="middle">'
        f'The measured result \u2014 41 probes against Codex\u2019s own checker</text>',
        f'<text x="600" y="98" font-family="sans-serif" font-size="19" '
        f'fill="{MUTED}" text-anchor="middle">'
        f'Pinned codex-cli 0.149.0 \u00b7 the question: how often does the '
        f'rulebook answer at all?</text>',
    ]
    for key, title in (("pre", "Before the fix"), ("post", "After the fix")):
        x = COL_X[key]
        counts = pre if key == "pre" else post
        els.append(f'<rect x="{x}" y="132" width="{COL_W}" height="320" '
                   f'rx="14" fill="{CARD}" stroke="{BORDER}" />')
        els.append(f'<text x="{x + 24}" y="176" font-family="sans-serif" '
                   f'font-size="24" font-weight="bold" fill="{TEXT}">{title}</text>')
        for i, label in enumerate(ORDER):
            y = ROWS_TOP + i * ROW_H
            els.append(bar_row(x + 24, y, label, counts[label],
                               deltas[label] if key == "post" else ""))
    els.append(f'<rect x="60" y="484" width="1080" height="104" rx="14" '
               f'fill="{CARD}" stroke="{TEAL}" stroke-width="2" />')
    els.append(f'<text x="600" y="528" font-family="sans-serif" font-size="22" '
               f'fill="{TEXT}" text-anchor="middle">'
               f'The fix moved 2 spellings from unknown to forbidden.</text>')
    els.append(f'<text x="600" y="562" font-family="sans-serif" font-size="22" '
               f'fill="{TEXT}" text-anchor="middle">'
               f'20 probes still get no decision \u2014 that is the finding.</text>')
    els.append(f'<text x="600" y="616" font-family="sans-serif" font-size="15" '
               f'fill="{MUTED}" text-anchor="middle">'
               f'Sealed post-fix bundle \u00b7 Merkle 5a974fe6\u2026</text>')
    els.append('</svg>')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(els) + "\n")
    print(f"wrote {OUT} (pre={pre}, post={post})")


if __name__ == "__main__":
    sys.exit(main())
