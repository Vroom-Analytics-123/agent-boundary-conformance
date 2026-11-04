# v1 adapter results (paper route) -- read this first

This bundle seals the v1 ADAPTER (paper) results: the same 24 scenarios
evaluated through each harness's documented decision semantics, NOT through
live agent sessions. No effects were observed here; `harm_executed` is False
by construction and is NOT a safety claim. Decisions only.

Source files (both from public main, byte-identical copies in this bundle):
- remeasure-v1-results.json -- the results file (methods + tallies + findings
  + 24 rows). Its `methods` block names the route per harness; its
  `badge_policy` states these results do NOT change any scorecard badge
  until verified sealed bundles exist.
- scenarios-v1.json -- the 24 scenarios (generated 2026-11-03 by Meta's
  muse-spark-1.3 via the Meta Model API; human-reviewed, kept verbatim).

No adapter runner is on main for these five routes (except the separate
goose-adapter-v1 paper item, which is a DIFFERENT item and is NOT in this
bundle). The bundle therefore carries the results + scenarios files plus
this note, and the Merkle root commits to the 120 per-harness decisions.

Pi and Goose notes from the results file: Pi ships no permission system
(README statement re-confirmed 2026-11-03); Goose had no config yet at
that date (permission surface is config-file based, no CLI flags).
