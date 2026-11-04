#!/usr/bin/env python3
"""Build the docs/assets/ visuals deterministically from committed evidence.

Deterministic: a pure function of committed inputs (sealed bundles,
measurement-routes JSON). Numbers on the charts come from the evidence
bundles, not from hand-typed constants — the cross-check against the bundles
is in CI via tests/test_scorecard_v1.py and the script's own assertions.

Outputs (docs/assets/):
  decisions_donut.png   — native decision distribution, 41-case main corpus
  three_layers.png      — the three layers Boundary Measurement compares
                          (founder model: Layer 1 = what the rules decide;
                          Layer 2 = the approval moment; Layer 3 = what
                          actually happens — ground truth)

Route assignments live in docs/MEASUREMENT_ROUTES.md (data:
docs/assets/measurement-routes-current.json, also read by mcp/server.py).
The retired route-matrix graphic (docs/assets/measurement_routes.png,
removed Nov 3, 2026 as redundant with MEASUREMENT_ROUTES.md and stale
at 8 harnesses) is no longer generated.
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
    fig.patch.set_facecolor("#0F1B2D")
    ax.set_facecolor("#0F1B2D")
    wedges, _ = ax.pie(
        vals,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
        startangle=90,
        colors=[COLORS[k] for k in order],
    )
    ax.text(0, 0.08, "41/41\npass", ha="center", va="center",
            fontsize=20, fontweight="bold", color="#E8EDF3")
    ax.text(0, -0.22, "41-case corpus", ha="center", va="center",
            fontsize=10, color="#AAB4C4")
    _leg = ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(0.92, 0.5),
              fontsize=11, frameon=False, title="Native decisions",
              title_fontsize=11, labelcolor="#E8EDF3")
    _leg.get_title().set_color("#AAB4C4")
    ax.set_title("Decision breakdown — pinned native oracle\n"
                 f"codex-cli 0.149.0 · six agreeing runs", fontsize=13,
                 fontweight="bold", pad=14, color="#E8EDF3")
    fig.text(0.5, 0.055,
             f"Sealed bundle Merkle root {merkle[:16]}…",
             ha="center", fontsize=8.5, color="#8A94A6")
    fig.text(0.5, 0.015,
             "54% unknown is a property of this synthetic probe set — never a real-world rate.",
             ha="center", fontsize=8.5, color="#8A94A6")
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    out = ASSETS / "decisions_donut.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def three_layers():
    fig, ax = plt.subplots(figsize=(9.0, 4.6), dpi=150)
    fig.patch.set_facecolor("#0F1B2D")
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)

    ax.text(5, 4.55, "The three layers Boundary Measurement compares",
            fontsize=14, fontweight="bold", color="#E8EDF3", ha="center",
            va="top")

    # Founder model (2026-10-22): Layer 1 = what the rules decide; Layer 2 =
    # the approval moment; Layer 3 = what actually happens (observed effect)
    # — ground truth, the most important layer.
    boxes = [
        (0.35, 1.15, 2.7, 2.4, "#1B2A42",
         "Layer 1 ·\nWhat the rules\ndecide", "the paper test\nthe harness's own\ndecision surface"),
        (3.65, 1.15, 2.7, 2.4, "#2A3D5E",
         "Layer 2 ·\nThe approval\nmoment", "the human/classifier\ngate: ask, approve,\noverride"),
        (6.95, 1.15, 2.7, 2.4, "#E8A838",
         "Layer 3 ·\nWhat actually\nhappens", "the live test\nobserved runtime\noutcome —\nGROUND TRUTH"),
    ]
    _tc = ["#E8EDF3", "#E8EDF3", "#1B2A42"]
    for (x, y, w, h, bg, title, body), tc in zip(boxes, _tc):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor=bg, edgecolor="#223452", linewidth=1.2))
        ax.text(x + w / 2, y + h - 0.30, title, ha="center", va="top",
                fontsize=11, fontweight="bold", color=tc, linespacing=1.4)
        ax.text(x + w / 2, y + h - 1.10, body, ha="center", va="top",
                fontsize=10, color=tc, linespacing=1.5)

    # Arrows between layers
    for xa, xb in [(3.05, 3.65), (6.35, 6.95)]:
        ax.annotate("", xy=(xb, 2.35), xytext=(xa, 2.35),
                    arrowprops=dict(arrowstyle="-|>", color="#AAB4C4",
                                    lw=1.6, shrinkA=2, shrinkB=2))

    fig.text(0.5, 0.16,
             "Cross-Examination compares the layers against each other —\n"
             "a disagreement between any two is a finding.",
             ha="center", fontsize=9.5, color="#AAB4C4")
    fig.text(0.5, 0.07,
             "Layer 3 is ground truth: paper findings are provisional until the live test\n"
             "confirms or refutes them. Silence is reported as unknown — never as allow.",
             ha="center", fontsize=9.5, color="#AAB4C4")
    out = ASSETS / "three_layers.png"
    fig.savefig(out)  # fixed canvas: no tight-crop
    plt.close(fig)
    return out


def main():
    counts, merkle, pin = load_counts()
    # Cross-check the two headline numbers against the bundle's own verdicts.
    assert counts["unknown"] == 22 and counts["allow"] == 6 \
        and counts["prompt"] == 4 and counts["forbidden"] == 9, counts
    for path in (donut(counts, merkle, pin), three_layers()):
        print("wrote", path)


if __name__ == "__main__":
    sys.exit(main())
