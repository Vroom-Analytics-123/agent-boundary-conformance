# Live reference-agent rollout — v1 (Nov 3, 2026)

Five of six agents measured live on the 24 v1 scenarios, two model arms
(cheaperinference beam; Meta muse-spark-1.1), each run twice: 480 runs.
Omnigent is blocked (driver source failed a safety check) — see SUMMARY.md.

Contents: SUMMARY.md (method, per-cell tallies, blockers), tallies.json
(machine-readable cell counts re-tallied from the record files at
publication time), runners/ (the drivers and proxy as run).

Scenarios are the v1 set at framework/scorecard/scenarios-v1.json.
Runners expect a scenarios file at /tmp/scenarios-v1.json when re-run;
copy that file there first. Per-run record files (with scratch fixtures)
are retained locally and are not published here.
