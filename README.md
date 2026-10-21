# Agent Boundary Conformance (working name — not trademark-cleared)

Local-first conformance tester for AI coding-agent security boundaries: it checks whether a developer's *intended* restrictions match what the harness's native policy interface *actually decides* — pass / fail / unknown, with evidence. It is not a scanner, not a firewall, and it never certifies a harness as "secure."

**Status:** Sprint Oct 21–27, 2026. Day 0 complete (smoke test verified, see `evidence/`). Day 1 baseline in progress.
**Plan of record:** `~/workspace/your_files/agent-boundary-conformance-execution-brief.md` (avan's evaluation + execution brief, Oct 20) and the source master plan docx in `~/workspace/user/files/`.
**Kill criterion:** Day 7 — must show one useful result the baselines (Snyk Agent Scan, harness-eval, agent-security-harness, native Codex) miss or explain poorly, or we stop and publish honestly.

Layout: `security/` invariant contracts · `fixtures/` synthetic policies + cases · `evidence/` verified run records · `docs/` baseline + design docs. Code lands Day 2–3.
