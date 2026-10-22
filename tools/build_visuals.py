#!/usr/bin/env python3
"""Build the docs/assets/ visuals deterministically from committed evidence.

Deterministic: a pure function of committed inputs (sealed bundles, tier
matrix JSON). Numbers on the charts come from the evidence bundles, not from
hand-typed constants — the cross-check against the bundles is in CI via
tests/test_scorecard_v1.py and the script's own assertions.

Outputs (docs/assets/):
  decisions_donut.png  — native decision distribution, 41-case main corpus
  tier_matrix.png      — the five-harness tier matrix
  three_layers.png     — the three layers Boundary Measurement compares
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "docs" / "assets"

# Accent palette: distinguish "unknown" (the finding) without implying danger.
COLORS = {
    "allow": "#2f7d4f",
    "prompt": "#d9a62e",
    "forbidden": "#b3402e",
    "unknown": "#5b7ba5",
}

FONT = {"family": "sans-serif"}


def load_counts():
    bundle = json.loads((REPO / "evidence" / "day6-2026-10-26" / "bundle.json").read_text())
    assert bundle["status"] == "valid", "Day-6 bundle must be valid"
    assert bundle["verdicts"]["pass"] == 41 and bundle["verdicts"]["fail"] == 0
    counts = {}
    for f in bundle["findings"]:
        d = f["actual_decision"]
        assert d in COLORS, f"unexpected decision {d}"
        counts[d] = counts.get(d, 0) + 1
    assert sum(counts.values()) == 41, counts
    merkle = bundle["merkle"]["root"]
    return counts, merkle, bundle["pinned"]["binary_sha256"][:8]


def donut(counts, merkle, pin):
    order = ["allow", "prompt", "forbidden", "unknown"]
    vals = [counts[k] for k in order]
    labels = [f"{k}\n{v}" for k, v in zip(order, vals)]

    fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=150)
    fig.patch.set_facecolor("white")
    wedges, _ = ax.pie(
        vals,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
        startangle=90,
        colors=[COLORS[k] for k in order],
    )
    ax.text(0, 0.08, "41/41\npass", ha="center", va="center",
            fontsize=20, fontweight="bold", color="#222222")
    ax.text(0, -0.22, "41-case corpus", ha="center", va="center",
            fontsize=10, color="#666666")
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(0.92, 0.5),
              fontsize=11, frameon=False, title="Native decisions",
              title_fontsize=11)
    ax.set_title("Decision breakdown — pinned native oracle\n"
                 f"codex-cli 0.149.0 · six agreeing runs", fontsize=13,
                 fontweight="bold", pad=14, color="#222222")
    fig.text(0.5, 0.055,
             f"Sealed bundle Merkle root {merkle[:16]}…",
             ha="center", fontsize=8.5, color="#777777")
    fig.text(0.5, 0.015,
             "54% unknown is a property of this synthetic probe set — never a real-world rate.",
             ha="center", fontsize=8.5, color="#777777")
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    out = ASSETS / "decisions_donut.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def tier_matrix():
    tm = json.loads((REPO / "evidence" / "reports" / "day6-scorecard" / "tier-matrix.json").read_text())
    hs = tm["harnesses"]
    assert len(hs) == 5, [h["harness"] for h in hs]

    rows = []
    for h in hs:
        measured = "measured verdicts" if h["tier"] == "T1" else "no verdicts measured"
        rows.append([h["harness"], h["tier"],
                     h["oracle_type"].replace("-", " "),
                     measured, h["evidence_class"]])
    # Deterministic presentation order: T1 first, then T2 in framework order.
    rows.sort(key=lambda r: (0 if r[1] == "T1" else 1, r[0] != "codex", r[0]))

    fig, ax = plt.subplots(figsize=(9.6, 4.6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(0.02, 0.94, "Five-harness tier matrix (Day 6, 2026-10-21)",
            fontsize=14, fontweight="bold", color="#222222", ha="left", va="top")
    ax.text(0.02, 0.86,
            "A harness is described by its tier, never as generically 'supported'.",
            fontsize=10.5, color="#555555", ha="left", va="top")

    cols = ["Harness", "Tier", "Oracle type", "Verdicts", "Evidence class"]
    widths = [0.19, 0.09, 0.24, 0.26, 0.18]
    x0 = 0.02
    y_top = 0.78
    rh = 0.095

    def cell(x, y, w, h, text, **kw):
        ax.add_patch(plt.Rectangle((x, y), w, h, fill=kw.pop("fill", True),
                                   facecolor=kw.pop("facecolor", "white"),
                                   edgecolor="#cccccc", linewidth=1))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=kw.pop("fontsize", 10.5), color=kw.pop("color", "#222222"),
                fontweight=kw.pop("fontweight", "normal"), wrap=True)

    x = x0
    for c, w in zip(cols, widths):
        cell(x, y_top - rh, w, rh, c, facecolor="#2b3a4a", color="white",
             fontweight="bold", fontsize=10.5)
        x += w

    tier_colors = {"T1": "#e8f2ea", "T2": "#fdf3e0"}
    y = y_top - rh
    for r in rows:
        y -= rh
        x = x0
        face = tier_colors.get(r[1], "white")
        for c, w in zip(r, widths):
            fw = "bold" if w == 0.09 else "normal"
            cell(x, y, w, rh, c, facecolor=face, fontweight=fw,
                 fontsize=10 if len(c) > 22 else 10.5)
            x += w

    fig.text(0.02, 0.03,
             "Promotion condition: a vendor ships a deterministic offline "
             "'evaluate this command against this policy' entrypoint at a pinned "
             "version (T2\u2192T1).\n"
             "Leading candidate: Amp (only vendor besides OpenAI with a shipped "
             "permission-test command).",
             fontsize=8.5, color="#777777", ha="left", va="bottom")
    fig.tight_layout()
    out = ASSETS / "tier_matrix.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def three_layers():
    fig, ax = plt.subplots(figsize=(9.0, 4.6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)

    ax.text(5, 4.55, "The three layers Boundary Measurement compares",
            fontsize=14, fontweight="bold", color="#222222", ha="center",
            va="top")

    boxes = [
        (0.35, 1.15, 2.7, 2.4, "#2b3a4a",
         "1 · Stated intent", "invariants.yaml\nthe promises"),
        (3.65, 1.15, 2.7, 2.4, "#5b7ba5",
         "2 · Native decision", "rules / approval /\nsandbox layers"),
        (6.95, 1.15, 2.7, 2.4, "#8a6d3b",
         "3 · Observed effect", "what observably\nhappened"),
    ]
    for x, y, w, h, bg, title, body in boxes:
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor=bg, edgecolor="#1d2733", linewidth=1.2))
        ax.text(x + w / 2, y + h - 0.30, title, ha="center", va="top",
                fontsize=11.5, fontweight="bold", color="white")
        ax.text(x + w / 2, y + h - 0.75, body, ha="center", va="top",
                fontsize=10, color="white", linespacing=1.5)

    # Arrows between layers
    for xa, xb in [(3.05, 3.65), (6.35, 6.95)]:
        ax.annotate("", xy=(xb, 2.35), xytext=(xa, 2.35),
                    arrowprops=dict(arrowstyle="-|>", color="#444444",
                                    lw=1.6, shrinkA=2, shrinkB=2))

    fig.text(0.5, 0.13,
             "Measured: intent vs decision per harness version (REPRO on the native oracle).",
             ha="center", fontsize=10, color="#555555")
    fig.text(0.5, 0.06,
             "Silence is reported as unknown with layer attribution — never as allow (INV-004/INV-005).",
             ha="center", fontsize=10, color="#555555")
    out = ASSETS / "three_layers.png"
    fig.savefig(out)  # fixed canvas: no tight-crop
    plt.close(fig)
    return out


def main():
    counts, merkle, pin = load_counts()
    # Cross-check the two headline numbers against the bundle's own verdicts.
    assert counts["unknown"] == 22 and counts["allow"] == 6 \
        and counts["prompt"] == 4 and counts["forbidden"] == 9, counts
    for path in (donut(counts, merkle, pin), tier_matrix(), three_layers()):
        print("wrote", path)


if __name__ == "__main__":
    sys.exit(main())
