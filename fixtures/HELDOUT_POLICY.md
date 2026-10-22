# Held-out corpus policy

The 41-case fixture corpus is split into a public shard (21 cases,
`fixtures/corpus_public.json`, committed) and a held-out shard (20 cases,
generated locally as `fixtures/corpus_heldout.json` — **intentionally not
committed**; it is in `.gitignore`).

Why: the contamination risk for this project is not a model memorizing our
fixtures — it is vendors (or us) tuning to the public corpus (Goodhart) and
corpus-design choices masquerading as population statistics. The held-out
shard exists so published-corpus tuning is detectable: public vs held-out
pass rates are reported separately in every evidence bundle
(`docs/SCIENTIFIC_REVIEW_ADDENDUM.md`, §e, adopted from the eval-science
literature and the CAPE-Bench exemplar).

Rules for the held-out shard:
1. Never published, never logged, never quoted — not even to Anish in chat.
   Bundle reports carry only its hash and aggregate pass/fail counts.
2. Only its SHA-256 is committed (`fixtures/corpus_manifest.json`, the
   pre-registration, every evidence bundle). Anyone with the shard file can
   verify it matches the committed hash.
3. Rotate per harness release: when the pinned codex version changes, author
   a fresh held-out shard and record the rotation in the manifest.
4. The Day-2 run executes all 41 cases (public + held-out); findings are
   tagged with their shard. Corpus statistics are always labelled as corpus
   results, never population rates.
