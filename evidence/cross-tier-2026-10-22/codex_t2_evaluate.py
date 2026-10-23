#!/usr/bin/env python3
"""T2 config-evaluation of Codex execpolicy semantics (documented only).

STEP 1 of the cross-tier study: a documentation-faithful T2 evaluator for the
SAME policies the T1 oracle (codex-cli 0.149.0, `codex execpolicy check`)
decided on. Comparing its per-case output against the sealed T1 ground truth
measures how much a documentation-faithful evaluation can be trusted where no
oracle exists.

Documented semantics modelled (with source for each rule):

  S1. token-prefix match: prefix_rule(pattern=[t1..tn], decision=D) matches a
      command iff the command's argv begins with exactly those n tokens
      (token-prefix, NOT path-prefix). Source: fixtures/policies/
      protected_records.rules header comment (REPRO Day 3) and the native
      `matchedPrefix` shapes in the sealed T1 bundles, e.g. PA-01 matches
      ["rm","-rf","/records/health"] while PA-02 (["rm","-rf",
      "/records/health/db.sqlite"]) matches nothing.
  S2. most-restrictive-wins: across all matching rules, the decision is
      forbidden > prompt > allow, independent of rule order and pattern
      specificity. Source: evidence/day1-baseline-2026-10-21/
      precedence_results.json (prec_a..prec_f reruns; DOC + REPRO).
  S3. resolve_host_executables: when true, argv[0] is resolved to its basename
      before matching (modeled here as os.path.basename; no actual host
      lookup — F-13d shows a nonexistent path /nonexistent/rm resolving to
      basename "rm"). Source: CLI flag name/adapter manifest
      (adapters/codex.v0.manifest.json) + fixture behaviour
      (F-13d/F-13R/F-14R/F-14bR ground truth agrees with basename matching).
  S4. no-match -> unknown: when no rule matches, the rules layer has no
      decision; we report "unknown". Source: INV-005; adapters/
      codex.v0.manifest.json ("No-match yields no decision at the rules
      layer... Documented in codex-cli help and verified by replay (DOC +
      REPRO)"); F-05 note ("unmatched must be reported as unknown").
  S5. argv is evaluated as passed: the evaluator takes the fixture's argv
      verbatim; it does not split on && / | / ; (native evaluates the leading
      segment only — F-11a, F-12a notes, Day-1 verified), which falls out of
      token-prefix-from-position-0 naturally.

Deliberately NOT modelled (ceilings, listed honestly):
  C1. The full host executable resolution semantics of native
      --resolve-host-executables (PATH lookup, symlinks, relative "./"
      forms): only the basename is modeled. No fixture resolves=true uses a
      form where basename and real resolution differ, so this ceiling does not
      fire on the corpus.
  C2. Anything below the rules layer: approval-policy outcomes and sandbox
      confinement are separate layers (adapters/codex.v0.manifest.json layer
      vocabulary). The T1 ground truth compared here is the rules-layer
      decision (actual_decision in the sealed bundles).
  C3. Native exit-code / JSON-shape details (matchedRules serialization):
      irrelevant to the decision comparison.

Usage:
  python3 codex_t2_evaluate.py --out evidence/cross-tier-2026-10-22/

Writes:
  codex_t2_fidelity_public.json          (committable: public-shard per-case
                                          rows + heldout aggregate counts)
  codex_t2_fidelity_heldout.local.json  (heldout per-case rows; gitignored)

Stdlib only. Never executes the codex binary.
"""

import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RULE_RE = re.compile(
    r'^prefix_rule\s*\(\s*pattern\s*=\s*\[(?P<pat>[^\]]*)\]\s*,\s*'
    r'decision\s*=\s*"(?P<dec>allow|prompt|forbidden)"\s*\)'
)
TOKEN_RE = re.compile(r'"([^"]*)"')

RESTRICTIVENESS = {"allow": 0, "prompt": 1, "forbidden": 2}
DECISIONS = ("allow", "prompt", "forbidden", "unknown")

CORPUS_PUBLIC = os.path.join(REPO, "fixtures/corpus_public.json")
CORPUS_HELDOUT = os.path.join(REPO, "fixtures/corpus_heldout.json")
PROT_PUBLIC = os.path.join(REPO, "fixtures/protected_records_public.json")
PROT_HELDOUT = os.path.join(REPO, "fixtures/protected_records_heldout.json")
GT_CORPUS = os.path.join(REPO, "evidence/postfix-2026-10-22/bundle.json")
GT_PROT = os.path.join(REPO, "evidence/postfix-2026-10-22/bundle-protected.json")

ORACLE_DESC = ("post-fix sealed bundles: evidence/postfix-2026-10-22/bundle.json "
               "(41-case corpus) + bundle-protected.json (protected family), "
               "pinned codex-cli 0.149.0, sha256 "
               "bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827")


def parse_rules(path):
    """Parse a Starlark prefix_rule rules file into [(tokens, decision)]."""
    rules = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = RULE_RE.match(line)
            if not m:
                raise ValueError("unparseable rule line %s:%d: %r" % (path, lineno, line))
            tokens = TOKEN_RE.findall(m.group("pat"))
            rules.append((tokens, m.group("dec")))
    return rules


def evaluate(argv, rules, resolve_host_executables):
    """Documented-semantics decision. Returns (decision, [matched rule indices])."""
    argv = list(argv)
    if resolve_host_executables and argv:  # S3: basename of argv[0]
        argv[0] = os.path.basename(argv[0])
    matched = [
        (i, dec) for i, (pat, dec) in enumerate(rules)
        if argv[:len(pat)] == pat  # S1: exact token-prefix match
    ]
    if not matched:  # S4: no-match -> unknown
        return "unknown", []
    # S2: most restrictive of the matching decisions wins.
    winner = max(matched, key=lambda t: RESTRICTIVENESS[t[1]])
    return winner[1], [i for i, _ in matched]


def load_fixtures():
    fixtures = []
    for path, shard in ((CORPUS_PUBLIC, "public"), (CORPUS_HELDOUT, "held-out"),
                        (PROT_PUBLIC, "public"), (PROT_HELDOUT, "held-out")):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        family = "corpus" if "corpus" in path else "protected"
        for c in data["fixtures"]:
            fixtures.append({
                "fixture_id": c["id"],
                "family": family,
                "shard": shard,
                "argv": c["argv"],
                "rules": os.path.join(REPO, c["rules"]),
                "resolve_host_executables": c.get("resolve_host_executables", False),
            })
    return fixtures


def load_ground_truth():
    """Per-fixture oracle actual_decision from the sealed post-fix bundles."""
    gt = {}
    for path in (GT_CORPUS, GT_PROT):
        with open(path, encoding="utf-8") as fh:
            bundle = json.load(fh)
        def walk(x):
            if isinstance(x, dict):
                if "actual_decision" in x and "fixture_id" in x:
                    gt[x["fixture_id"]] = {
                        "oracle": x["actual_decision"],
                        "shard": x.get("corpus_shard"),
                    }
                else:
                    for v in x.values():
                        walk(v)
            elif isinstance(x, list):
                for e in x:
                    walk(e)
        walk(bundle)
    return gt


def describe_cause(row, rules):
    """Human cause for a disagreement (or empty string for agreement)."""
    if row["agree"]:
        return ""
    argv, pat_rules = row["argv"], rules
    n_match = len(row["matched_rule_indexes"])
    oracle, t2 = row["oracle"], row["t2"]
    # Characterize the semantic rule / ceiling involved.
    if n_match == 0 and t2 == "unknown":
        if oracle in ("allow", "prompt", "forbidden"):
            return ("Documented prefix semantics found no matching rule (token-prefix "
                    "S1), but the oracle returned '%s': evaluator ceiling — undocumented "
                    "native matching behaviour." % oracle)
    if n_match == 0 and oracle == "unknown":
        # Both unknown but different cause paths? They agree, so unreachable.
        return ""
    if row.get("resolve_host_executables") and argv and "/" in argv[0]:
        return ("resolve_host_executables=true (S3): evaluator models basename-only "
                "resolution; disagreement implies native host resolution did more "
                "(PATH lookup / symlink) or less than basename.")
    if n_match > 0 and t2 == "unknown":
        return ("internal inconsistency: rules matched but decision unknown")
    return ("Multiple rules matched (%d); most-restrictive-wins (S2) gave '%s' but "
            "oracle gave '%s': evaluator ceiling — undocumented native precedence "
            "or pattern interaction." % (n_match, t2, oracle))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    rules_cache = {}
    def rules_for(path):
        if path not in rules_cache:
            rules_cache[path] = parse_rules(path)
        return rules_cache[path]

    gt = load_ground_truth()
    rows = []
    missing = []
    for fx in load_fixtures():
        fid = fx["fixture_id"]
        g = gt.get(fid)
        if g is None:
            missing.append(fid)
            continue
        rules = rules_for(fx["rules"])
        decision, matched = evaluate(fx["argv"], rules, fx["resolve_host_executables"])
        rows.append({
            "fixture_id": fid,
            "family": fx["family"],
            "shard": g["shard"] or fx["shard"],
            "oracle": g["oracle"],
            "t2": decision,
            "agree": decision == g["oracle"],
            "matched_rule_indexes": matched,
            "resolve_host_executables": fx["resolve_host_executables"],
            "argv": fx["argv"],
        })
    for r in rows:
        r["cause"] = describe_cause(r, rules_for(
            os.path.join(REPO, "fixtures/policies/default.rules")))

    for r in rows:
        del r["argv"]  # keep argv out of emitted rows (fixtures carry them)

    public_rows = [r for r in rows if r["shard"] == "public"]
    heldout_rows = [r for r in rows if r["shard"] == "held-out"]

    def stats(sub):
        total = len(sub)
        agree = sum(1 for r in sub if r["agree"])
        by_class = {}
        for cls in DECISIONS:
            cls_rows = [r for r in sub if r["oracle"] == cls]
            if cls_rows:
                by_class[cls] = {
                    "n": len(cls_rows),
                    "agree": sum(1 for r in cls_rows if r["agree"]),
                    "rate": round(sum(1 for r in cls_rows if r["agree"]) / len(cls_rows), 4),
                }
        return {
            "n": total,
            "agree": agree,
            "disagree": total - agree,
            "agreement_rate": round(agree / total, 4) if total else None,
            "per_oracle_class": by_class,
        }

    dis_pub = [ {k: r[k] for k in ("fixture_id", "family", "oracle", "t2",
                 "matched_rule_indexes", "resolve_host_executables", "cause")}
                for r in public_rows if not r["agree"] ]

    public_out = {
        "schema": "codex-t2-fidelity.v1",
        "oracle": ORACLE_DESC,
        "evaluator": "evidence/cross-tier-2026-10-22/codex_t2_evaluate.py (documented semantics S1..S5; ceilings C1..C3)",
        "overall": stats(rows),
        "public_shard": stats(public_rows),
        "heldout_shard_aggregate": stats(heldout_rows),
        "public_per_case": [
            {k: r[k] for k in ("fixture_id", "family", "oracle", "t2", "agree", "cause")}
            for r in public_rows
        ],
        "public_disagreements": dis_pub,
        "missing_ground_truth": missing,
        "note": "Held-out per-case rows are local-only (codex_t2_fidelity_heldout.local.json, gitignored per fixtures/HELDOUT_POLICY.md); only aggregates appear here.",
    }
    with open(os.path.join(args.out, "codex_t2_fidelity_public.json"), "w") as fh:
        json.dump(public_out, fh, indent=2)

    heldout_out = {
        "schema": "codex-t2-fidelity.v1",
        "oracle": ORACLE_DESC,
        "heldout_per_case": [
            {k: r[k] for k in ("fixture_id", "family", "oracle", "t2", "agree", "cause",
                               "matched_rule_indexes", "resolve_host_executables")}
            for r in heldout_rows
        ],
    }
    with open(os.path.join(args.out, "codex_t2_fidelity_heldout.local.json"), "w") as fh:
        json.dump(heldout_out, fh, indent=2)

    s = stats(rows)
    print("cases:", s["n"], "agree:", s["agree"], "rate:", s["agreement_rate"])
    print("missing ground truth:", missing)
    for r in rows:
        if not r["agree"]:
            print("DISAGREE", r["fixture_id"], r["shard"], "oracle=", r["oracle"],
                  "t2=", r["t2"], "cause=", r["cause"])


if __name__ == "__main__":
    main()
