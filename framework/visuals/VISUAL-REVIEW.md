# Visual review — repo polish (Nov 3, 2026)

One palette for the whole repo: the scorecard's dark-navy family
(background `#0F1B2D`, cards `#1B2A42` / `#223452`, text `#E8EDF3` /
`#AAB4C4`, accents teal `#2AA5A0`, amber `#E8A838`, green `#3FA46A`,
red `#D95D4E`). Everything below was judged against "does this inspire
confidence?" — harshly. PNG proofs were rendered locally for verification
and are not committed; repo visuals stay SVG canonical (the two
matplotlib PNGs are the exception — they are generator outputs).

## Verdicts

| Visual | Verdict | Reason / change |
|---|---|---|
| `framework/visuals/how-it-works.svg` (NEW) | Polished | Replaces the old How-it-works PNG embed. Problem → rule → probe → three layers (compared, not chained) → finding → fix → re-measure, plus a Codex hero band (forbidden 9 → 11, sealed, re-measured) and the honest footer. Subtitle carries the positioning: early testing and assurance framework, inspector never enforcer. |
| `docs/assets/three_layers.png` | Was ugly, restyled | White background clashed with every dark SVG (the repo looked like a collage), and its arrows implied a pipeline when the point is comparison. Generator (`tools/build_visuals.py`) restyled to the dark-navy family; Layer 3 (ground truth) now amber with dark text. The README no longer embeds it — the new SVG above replaces it — but the script still generates it, so the file stays. |
| `docs/assets/decisions_donut.png` | Was off-palette, restyled | Same white-background collage problem. Generator restyled to the dark frame with light text. Wedge colors are semantic (allow/prompt/forbidden/unknown) and UNCHANGED; counts UNCHANGED (6/4/9/22, asserted by the generator against the day-6 bundle). Still embedded in "The measured result". |
| `framework/visuals/scorecard.svg` | Polished, untouched | Generated, data-frozen. |
| `framework/visuals/scorecard-v3.svg` | Polished, untouched | Generated, data-frozen, PROVISIONAL labelling intact. |
| `framework/visuals/concepts/concept-three-layers.svg` | Polished, minor fix | Accent strips overhung the cards' rounded corners (square corners poking out). Strips inset 8px each side. Text and data untouched. |
| `framework/visuals/concepts/concept-measurement-loop.svg` | Had a real defect, fixed | The return label ("and again, every version") was clipped at the left canvas edge. Moved inward (x 14 → 26); now fully visible. Strips inset as above. |
| `framework/visuals/concepts/concept-unknown-not-allow.svg` | Polished, minor fix | Strip insets only. |
| `framework/visuals/concepts/concept-most-restrictive-wins.svg` | Polished, minor fix | Strip insets only. |
| `framework/visuals/concepts/concept-bundle-anatomy.svg` | Polished, minor fix | Strip insets only. |
| `framework/visuals/concepts/concept-good-short-fix.svg` | Polished, minor fix | Strip insets only. |
| `framework/visuals/concepts/concept-transparency-reasonability.svg` | Polished, minor fix | Strip insets only. |
| `framework/visuals/concepts/concept-version-drift.svg` | Polished, untouched | No strips to fix; honest ILLUSTRATIVE labelling intact. |
| `framework/visuals/dimensions-at-a-glance.svg` | Polished, minor fix | Strip insets only. |
| `framework/visuals/layers-x-dimensions.svg` | Was cramped, fixed | Row-header descriptions were one word per line ("What / the / policy / decides"); merged to two clean lines each. Column headers hyphenated mid-word (TRANSPARE-ENCY, CUSTOMI-ZATION, REASON-ABILITY); now single lines. No wording changed. |
| `framework/visuals/version-drift.svg` | Polished, untouched | Honest ILLUSTRATIVE labelling intact; left-card whitespace noted, not worth a redraw. |
| `framework/visuals/hero.jpg` | Left untouched | No references found in the repo (code search, 0 hits). Possibly a leftover; parent to confirm whether to remove. |
| `evidence/reports/day6-scorecard-v3-postfix/measured-scorecard.svg` | Left untouched | Historical evidence artifact; never restyle evidence. |

## Data frozen

No number, score, band, tally, or finding changed anywhere in this
branch. Colours, layout, and explanation text only. The donut's counts
come from its source bundle and are re-asserted every time the generator
runs.

## Notes for the parent (not changed here — your call)

- **Donut framing:** the donut renders the day-6 bundle's "six agreeing
  runs" distribution (allow 6, prompt 4, forbidden 9, unknown 22), which
  equals the pre-fix distribution. The README text around it ("The
  measured result") does not label which run it is. The numbers are
  correct for their bundle; whether the caption should say so explicitly
  is a wording call, not a visual one.
- **Concept version labels:** several concept visuals cite "Claude Code
  2.1.307" — the version their reconstructed examples were built
  against, not the current CLI (2.1.318 in the Nov 3 smoke). They are
  accurate for their examples; updating them would be a data decision.
- **Removed from How-it-works (not deleted from the repo):** the
  route-by-route inventory now lives only in
  `docs/MEASUREMENT_ROUTES.md` (linked from the section), and the
  Codex-only mermaid flowchart is superseded by the new general diagram.
  Both are recoverable from git history if you want them back.
- **Demo use:** `how-it-works.svg` is built to double as a demo slide
  (1200×880, legible at full screen, no small text). The scorecard-whole
  and scores slides the demo needs are `scorecard.svg` /
  `scorecard-v3.svg` as they stand.
