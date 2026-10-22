#!/usr/bin/env python3
"""Cursor CLI Allowlist-mode T2 evaluation engine (config-evaluation).

Implements the permission semantics documented at
https://cursor.com/docs/cli/reference/permissions (retrieved 2026-10-22)
for the CLI token surface only:

  - Shell(commandBase): commandBase is the FIRST TOKEN of the command line;
    glob patterns supported; optional `command:args` syntax matches both
    command and arguments with globs.
  - Read(pathOrGlob), Write(pathOrGlob): glob patterns against paths.
  - WebFetch(domainOrPattern): `*` = all, `*.example.com` = subdomains,
    `example.com` = exact domain only.
  - Mcp(server:tool): `*` wildcards for server and tool.
  - Deny rules take precedence over allow rules (order-independent).
  - No matching rule -> the native layer PROMPTS (interactive approval).
    At the T2 config-evaluation layer this is unobserved, so per the
    framework vocabulary it is reported as `unknown` with layer attribution
    (never as allow; INV-005).

This is a labelled REIMPLEMENTATION of the vendor's documented matching
semantics, not an interrogation of the harness: every output is labelled
T2-evaluated. The real Cursor CLI (agent 2026.10.19-6bbf2c4) has no
check/evaluate decision-oracle subcommand (spike re-run 2026-10-22).

Documented assumptions (all recorded as translation ceilings in TEST_LOG.md):
  A1. A corpus case arrives as argv; the "command line" is argv joined with
      single spaces. The first token is argv[0]; the args string is the
      remainder after stripping leading whitespace. Shell-quoting is NOT
      reconstructed (no case in the corpus requires it).
  A2. Cursor has no documented executable-resolution concept (no analogue of
      codex --resolve-host-executables): first token is matched as given.
  A3. Glob flavor (docs name `*`, `?`, `**` but pin no library). Two subjects:
      - Shell command/args, WebFetch domains, Mcp server/tool: `*` crosses
        `/` (fnmatch semantics) — required by the docs' own worked examples:
        `Shell(curl:*)` = 'Allow curl with any arguments' must match
        'https://example.com' (slashes), and `WebFetch(*)` = 'matches all
        domains' must match dotted domains.
      - Read/Write paths: minimatch path semantics — `*`/`?` do not cross
        `/`, and `**/` matches zero or more segments (so `**/*.md` matches
        both `README.md` and `docs/x.md`).
  A4. `prompt` is not a config verb in Allowlist mode: prompt-intent rules are
      dropped at translation time (never forced into allow or deny); the
      resulting no-match reports unknown with the "prompt by default"
      attribution.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field

EVIDENCE_CLASS = "T2-evaluation (never interrogated)"


def _glob_to_regex(pattern: str) -> str:
    # minimatch-style path-glob semantics (assumption A3):
    #   `**/` matches zero or more path segments (so `**/*.md` matches
    #          both `README.md` and `docs/x.md`);
    #   `**`   matches any characters including `/`;
    #   `*`    matches any characters except `/`;
    #   `?`    matches one character except `/`.
    i, out = 0, ""
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 3] == "**/":
                out += "(?:.*/)?"
                i += 3
            elif pattern[i : i + 2] == "**":
                out += ".*"
                i += 2
            else:
                out += "[^/]*"
                i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return r"(?:%s)\Z" % out


def _glob(pattern: str, value: str) -> bool:
    # fnmatch semantics: `*` crosses `/` (used for Shell command/args,
    # WebFetch domains, Mcp server/tool — see assumption A3).
    return fnmatch.fnmatchcase(value, pattern)


def _glob_path(pattern: str, value: str) -> bool:
    # minimatch path semantics (used for Read/Write path subjects).
    return re.match(_glob_to_regex(pattern), value, re.DOTALL) is not None


UNKNOWN_LAYER = (
    "allowlist-rules-layer: no allow/deny token matched; native interactive "
    "Allowlist-mode behavior would prompt for approval — unobserved at the "
    "config-evaluation layer (T2, never interrogated)"
)

VOCAB = ("allow", "prompt", "forbidden", "unknown", "unmapped")


# --------------------------------------------------------------------------
# Token parsing / matching
# --------------------------------------------------------------------------

@dataclass
class Token:
    kind: str          # Shell | Read | Write | WebFetch | Mcp
    raw: str           # full token as written, e.g. "Shell(git:status*)"
    pattern: str       # inner pattern, e.g. "git:status*"

    @staticmethod
    def parse(raw: str) -> "Token":
        raw = raw.strip()
        if "(" not in raw or not raw.endswith(")"):
            raise ValueError(f"malformed permission token: {raw!r}")
        kind, inner = raw.split("(", 1)
        kind = kind.strip()
        inner = inner[:-1]
        if kind not in ("Shell", "Read", "Write", "WebFetch", "Mcp"):
            raise ValueError(f"unknown permission token kind: {kind!r}")
        return Token(kind=kind, raw=raw, pattern=inner)


def match_shell(token: Token, argv: list[str]) -> bool:
    """Docs: 'The commandBase is the first token in the command line.'
    Supports glob patterns and the optional `command:args` syntax.
    """
    if not argv:
        return False
    first = argv[0]
    args_str = " ".join(argv[1:]).lstrip()
    if ":" in token.pattern:
        cmd_pat, args_pat = token.pattern.split(":", 1)
        return _glob(cmd_pat, first) and _glob(args_pat, args_str)
    return _glob(token.pattern, first)


def match_read_write(token: Token, path: str) -> bool:
    """Read(pathOrGlob) / Write(pathOrGlob): glob patterns against paths."""
    return _glob_path(token.pattern, path)


def match_webfetch(token: Token, domain: str) -> bool:
    """Docs: `*` matches all domains; `*.example.com` matches subdomains;
    `example.com` matches that exact domain only."""
    return _glob(token.pattern, domain)


def match_mcp(token: Token, server: str, tool: str) -> bool:
    """Mcp(server:tool) with `*` wildcards for either component."""
    if ":" in token.pattern:
        srv_pat, tool_pat = token.pattern.split(":", 1)
    else:
        srv_pat, tool_pat = token.pattern, "*"
    return _glob(srv_pat, server) and _glob(tool_pat, tool)


# --------------------------------------------------------------------------
# Policy evaluation
# --------------------------------------------------------------------------

@dataclass
class Policy:
    allow: list[Token] = field(default_factory=list)
    deny: list[Token] = field(default_factory=list)
    source: str = ""

    @staticmethod
    def load(path: str) -> "Policy":
        doc = json.load(open(path))
        perms = doc["permissions"]
        return Policy(
            allow=[Token.parse(t) for t in perms.get("allow", [])],
            deny=[Token.parse(t) for t in perms.get("deny", [])],
            source=path,
        )


@dataclass
class Decision:
    decision: str            # allow | forbidden | unknown
    matched_deny: list[str]  # raw tokens that matched (deny wins)
    matched_allow: list[str] # raw tokens that matched
    notes: list[str]


def evaluate_shell(policy: Policy, argv: list[str]) -> Decision:
    """Deny takes precedence over allow; no match -> unknown (prompt-by-default,
    unobserved at T2)."""
    denied = [t.raw for t in policy.deny if match_shell(t, argv)]
    if denied:
        return Decision(
            decision="forbidden",
            matched_deny=denied,
            matched_allow=[],
            notes=["deny token matched; deny takes precedence over allow (docs)"],
        )
    allowed = [t.raw for t in policy.allow if match_shell(t, argv)]
    if allowed:
        return Decision(
            decision="allow",
            matched_deny=[],
            matched_allow=allowed,
            notes=[],
        )
    return Decision(
        decision="unknown",
        matched_deny=[],
        matched_allow=[],
        notes=[UNKNOWN_LAYER],
    )


def evaluate_case(policy: Policy, fixture: dict) -> dict:
    argv = list(fixture["argv"])
    evaluated_form = " ".join(argv)  # assumption A1
    dec = evaluate_shell(policy, argv)
    return {
        "fixture_id": fixture["id"],
        "argv": argv,
        "evaluated_form": evaluated_form,
        "evaluated_first_token": argv[0] if argv else None,
        "matched_deny": dec.matched_deny,
        "matched_allow": dec.matched_allow,
        "decision": dec.decision,
        "notes": dec.notes,
        "policy": policy.source,
        "expected": fixture.get("expected"),
        "kind": fixture.get("kind"),
        "maps_to": fixture.get("maps"),
        "evidence_class": EVIDENCE_CLASS,
    }


def policy_for_fixture(fixture: dict, default_policy: str, base_dir: str) -> str:
    """Precedence probes reference their own prec_*.rules files; the cursor
    translations live in adapters/cursor/policy/prec_*.json."""
    rules = fixture.get("rules", "")
    if "prec_" in rules:
        name = rules.rsplit("/", 1)[-1].replace(".rules", ".json")
        return f"{base_dir}/policy/{name}"
    if "protected_records.rules" in rules:
        return f"{base_dir}/policy/protected.json"
    return default_policy


def run(corpus_paths: list[str], default_policy: str, base_dir: str) -> list[dict]:
    results = []
    policy_cache: dict[str, Policy] = {}
    for path in corpus_paths:
        doc = json.load(open(path))
        for fx in doc["fixtures"]:
            ppath = policy_for_fixture(fx, default_policy, base_dir)
            if ppath not in policy_cache:
                policy_cache[ppath] = Policy.load(ppath)
            rec = evaluate_case(policy_cache[ppath], fx)
            rec["corpus_shard"] = doc.get("corpus_shard")
            rec["corpus_file"] = path
            results.append(rec)
    return results


def main(argv: list[str]) -> int:
    # usage: evaluate.py <base_dir> <default_policy> <corpus_json...> --out <out>
    if "--out" not in argv:
        print("usage: evaluate.py <base_dir> <default_policy> <corpus...> --out <out>", file=sys.stderr)
        return 2
    i = argv.index("--out")
    base_dir, default_policy, corpora, out = argv[0], argv[1], argv[2:i], argv[i + 1]
    results = run(corpora, default_policy, base_dir)
    json.dump(results, open(out, "w"), indent=1)
    print(f"evaluated {len(results)} cases -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
