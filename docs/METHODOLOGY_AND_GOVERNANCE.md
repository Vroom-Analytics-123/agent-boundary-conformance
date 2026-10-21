# Methodology & Governance — DRAFT for launch (not yet published)

Prepared 2026-10-21 so governance ships WITH the public launch, not after it. Nothing here is public until Anish approves the launch.

## Methodology commitments
1. **Pinned everything.** Every published number names the exact harness version, policy/config hashes, fixture corpus version, and runner version. A result that cannot be replayed from its bundle is withdrawn, not defended.
2. **Three evidence layers, never conflated.** Policy decision (native interface output), approval outcome (pinned-policy runtime probe), observed effect (sandboxed instrumentation). Each result is labelled with the layer(s) it actually measured.
3. **Unknowns stay unknown.** No-match results are reported as decision-coverage gaps with the governing layer named — never as bypasses, holes, or evasions. Effect claims are never inferred from decision data.
4. **Balanced corpus.** Fixtures include legitimate-task preservation controls (things that SHOULD be allowed) with the same prominence as divergence cases; false positives are published in the same table as findings.
5. **Counterexamples & corrections.** Anyone can file a counterexample against any published result. Confirmed errors are corrected in a public corrections log with the original preserved (append-only), and affected Index numbers are restated, not silently edited.
6. **Verifiability.** Corpus roots are anchored in a public transparency log with independent witness cosigning; verification tooling is free and offline-capable forever.

## Vendor relations (the embargo program)
- On each covered harness release, vendors receive their own results under a short embargo (target: 7 days) before publication: they may dispute (with evidence), fix, or comment — comments are published alongside results on request.
- Vendors may not suppress, delay beyond the embargo, or preview other vendors' results.
- Disputes are adjudicated on replayed evidence; the dispute and its resolution enter the public record.

## Independence
- No vendor funding for measurement work. Grant funding sources are listed publicly. Commercial revenue (hosted evidence, pilots) is firewalled from verdicts: paying customers receive the same verdicts the public corpus produces, and private-corpus results are labelled as such with methodology identical.
- Advisory circle members and any conflicts are named on the governance page.

## Non-claims (travel with every publication)
We do not certify any harness as "safe." We measure conformance between stated intent and native decisions/effects under pinned conditions. A pass is a measurement, not a guarantee; an unknown is a measurement, not an accusation.
