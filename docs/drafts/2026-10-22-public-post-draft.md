# DRAFT — first public results post (DO NOT PUBLISH)

Status: draft for Anish's approval only. Nothing posted, nothing pushed.
Source: the Day-1 baseline (docs/COMPETITOR_BASELINES.md) + the harness v0
runs, now hardened by Day 2 (hash-locked corpus, schemas v1, verified
evidence bundle). ~120 words.

---

Day 2 of building a conformance tester for coding agents, in public.

We wrote a 3-rule policy for Codex (allow `git status`, prompt on deploys,
forbid `rm -rf`) and replayed 41 probe cases against Codex's own policy
checker (codex-cli 0.149.0). Three independent runs now agree 41/41.

The direct commands decide exactly as written. But 22 of 41 cases — mostly
ordinary variants and wrapped forms of the forbidden command — get no
rules-layer decision at all. Our tester reports those as "unknown", never
as "allow", and every result ships with replayable, hash-stamped evidence.

Unknown doesn't mean the command would run — approval policy and the
sandbox decide that. It means your written policy, by itself, doesn't
decide it. That gap is what we're measuring.

Code + evidence once the repo is public.

---

Scope notes that must survive any edit of the above (Revision 2):
- 22/41 is a property of a synthetic probe corpus deliberately weighted
  toward wrappers/variants — never quote it as a real-world rate.
- "Unknown" is never "bypass", "evasion", or "hole".
- No claim rests on an unmatched rule alone.
