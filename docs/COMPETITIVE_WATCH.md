# Competitive Watch — market + standards (living document, opened 2026-10-23)

Who else occupies the agent-security field, what the standards bodies are doing,
and which circulating claims about this market are actually verified. This is
the **market-level** watch. It is distinct from the tool-level records
(`docs/COMPETITOR_BASELINES.md`, `docs/COMPETITIVE_EVIDENCE_MATRIX.md` — same
fixtures run against the closest tools) and from the novelty record
(`docs/SCIENTIFIC_REVIEW_ADDENDUM.md`).

**Label discipline (same as everywhere in this repo):** every entry is
**VERIFIED** (checked against a primary or solid secondary source, named) or
**REPORTED** (single-source, not independently confirmed). Vendor claims are
never entered as results. Entries carry the date checked; re-verify before
citing externally.

---

## 1. Runtime governance / enforcement competitors

### Geordie AI — VERIFIED (checked 2026-10-23)
- $30M Series A, May 2026, led by Balderton Capital; $36.5M total raised.
  Won the RSAC 2026 Innovation Sandbox.
- What they sell: enterprise AI-agent governance and runtime controls,
  including a remediation suite ("Beam", per their own materials) — agent
  inventory, oversight, and runtime governance for enterprises.
- **Classification: runtime-governance competitor, NOT a conformance
  measurer.** They govern agents at runtime; they do not independently
  measure whether a harness's declared rulebook matches what the harness
  enforces.
- Sources: company announcement via EINPresswire, May 28 2026; Forkast
  analysis of the round.

## 2. Incumbent roll-ups — VERIFIED (checked 2026-10-23, years corrected)

| Acquirer | Acquired | Year | Side of the field |
|---|---|---|---|
| Cisco | Robust Intelligence | 2024 | runtime / enforcement, bundled into platform |
| Palo Alto Networks | Protect AI | 2025 | runtime / enforcement, bundled into platform |
| SentinelOne | Prompt Security | 2025 | runtime / enforcement, bundled into platform |
| Check Point | Lakera | 2025 | runtime / enforcement, bundled into platform |

Pattern: the incumbents are buying AI-security capability to bundle into
existing platforms. Every one of these sits on the enforcement side — none is
an independent conformance measurement of vendor rulebooks.

## 3. Market context — REPORTED (single-source, checked 2026-10-23)

- ~$435M invested in AI agent security across 12 rounds, April–September
  2026 (Forkast analysis).
- SailPoint Horizons report (Oct 2026): 79% of enterprises run AI agents in
  production; only 2% have identity security in place.
- Treat both as REPORTED until independently confirmed; safe for internal
  sizing, not for external citation as fact.

## 4. Standards timeline — VERIFIED (checked 2026-10-23)

| When | What | Relevance to FinePrint |
|---|---|---|
| Dec 2025 | OWASP Top 10 for Agentic Applications | The risk taxonomy the field cites; risks, not measurements |
| Feb 2026 | NIST AI Agent Standards Initiative | US standards attention on agent systems; framework-level, voluntary |
| Feb 2026 | UC Berkeley Agentic AI Risk-Management Standards Profile | Academic standards profile for agentic risk management |
| Sep 2026 | OWASP Agent Control Standard | Runtime **enforcement** middleware hooks — an adjacent standard on the enforcement side, **not** measurement |

Trajectory: standards are converging on oversight and continuous testing of
agents. None of the above independently measures a harness's declared rules
against its enforced decisions.

## 5. Explicitly NOT verified — do not quote

> **Claim:** "In August 2026, industry glossaries officially adopted
> 'Continuous Agent Testing' / 'Agent Conformance Checking' as required
> practices under the NIST AI RMF."

**Status: NOT VERIFIED (checked 2026-10-23).** No supporting source was
found, and the claim mischaracterizes the NIST AI RMF, which is voluntary
guidance — it does not impose "required practices" of this kind. This claim
circulates in secondary AI-generated market commentary. **No FinePrint
document, deck, or filing may quote it.** The verified standards entries in
§4 are what may be cited.

## 6. Synthesis (our doctrine, one line)

The field sells walls (runtime enforcement) and inventories; independent
conformance measurement of the rulebook — declared rules vs. enforced
decisions, with sealed evidence — remains the open seat. **(HYPOTHESIS —
consistent with the narrowed novelty framing in
`docs/SCIENTIFIC_REVIEW_ADDENDUM.md`; a gap hypothesis, not proven novelty.)**

---

*Maintenance: add entries only with a source and a checked date; demote stale
VERIFIED entries to REPORTED if the source disappears; never promote a
REPORTED entry without a second, independent source.*
