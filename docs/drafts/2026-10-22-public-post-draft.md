# DRAFT — first public results post (DO NOT PUBLISH)

Status: draft for Anish's approval only. Nothing posted, nothing published.
Source: the sealed Day-6 evidence bundle (`evidence/day6-2026-10-26/bundle.json`,
Merkle root `003bfbb3…`) + `docs/daily/2026-10-27.md` (verdict NARROW) +
`docs/FRAMEWORK.md` (five-harness tiers). Refreshed by the polish pass.
~210 words.

---

Week one of measuring what AI coding agents' rulebooks actually decide, in
public.

The building-inspector framing: an inspector doesn't declare a building
safe. She checks it against the code its owner filed — item by item, what
matches and what doesn't. That's what this project does for agent policies:
the harness's own decision engine is the thing under inspection.

We wrote two sample policies for Codex (codex-cli 0.149.0): three command
rules, plus a protected-records policy for a health-records directory. 41
probe cases replayed against Codex's own checker; six independent runs agree
byte-identically. Wherever the rulebook answers, we agree (41/41 pass). The
finding is how often it doesn't answer: 22 of 41 native decisions are
explicit unknowns — ordinary variants (`rm -fr`) and wrapped forms
(`bash -lc`) the written rules never address. Unknown is reported with its
layer attached, never as allow.

The project is now a harness-neutral framework: Codex measured at T1;
Claude Code, Cursor, Gemini CLI, and OpenCode tiered at T2 — documented
enough to evaluate, no decision oracle yet, so no verdicts claimed there.

The verdict on the week's kill test is NARROW: the method is proven, but a
public Index on one measured harness would overclaim — so the repo stands as
the method, limitations on its face.

Code + sealed evidence once the repo is public.

---

Scope notes that must survive any edit of the above (Revision 2):
- 22/41 is a property of a synthetic probe corpus deliberately weighted
  toward wrappers/variants — never quote it as a real-world rate.
- "Unknown" is never "bypass", "evasion", or "hole".
- No claim rests on an unmatched rule alone.
- All results are pre-fix (the Day-5 fix diff is unapproved and unapplied);
  any public version carries the PRE-FIX banner.
- One measured harness (Codex T1); the four T2 rows carry no measured
  verdicts, and the draft claims none.
- No grant or publication claim beyond the narrowed novelty statement.
