#!/usr/bin/env python3
"""Gemini CLI T2 evaluation engine.

Reimplements the TOML policy-engine decision semantics of
@google/gemini-cli@0.65.0 from vendor documentation (labelled evaluation,
never interrogated — no native oracle exists at the pinned version).

Primary sources (retrieved 2026-10-22):
- https://geminicli.com/docs/reference/policy-engine
    rule matching; "the rule with the highest priority wins"; first match at
    highest final_priority determines the outcome; final_priority =
    tier_base + toml_priority/1000; tiers Admin > User > Workspace/Extension >
    Default; commandPrefix/commandRegex/argsPattern; modes; interactive;
    allowRedirection; ask_user treated as deny in non-interactive mode;
    default policies (run_shell_command defaults to ask_user; yolo-mode
    high-priority allow-all); toolName wildcards.
- https://geminicli.com/docs/tools/shell/
    chain splitting on &&, ||, ; with per-part validation; any part
    disallowed -> whole command blocked; prefix matching; blocklist checked
    first (documented for the deprecated tools.core/tools.exclude surface;
    the TOML engine expresses this via high-priority deny rules).
- https://geminicli.com/docs/reference/configuration/
    YOLO cannot be enabled from settings.json (CLI flag only); TOML rules may
    be scoped modes=["yolo"].

Pinned harness: @google/gemini-cli@0.65.0.
Route: config-evaluation (T2). Deterministic: pure function of inputs.
"""

import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants / documented semantics
# ---------------------------------------------------------------------------

# Tier bases per the policy-engine reference TIER TABLE
# (Default 1, Extension 2, Workspace 3, User 4, Admin 5).
# DOC-vs-DOC conflict (recorded in TEST_LOG.md): the page's worked examples
# use bases 1/2/3/4 for Default/Workspace/User/Admin. The ORDERING
# Admin > User > Workspace/Extension > Default is identical either way, which
# is the only property decision outcomes depend on.
TIER_BASE = {
    "default": 1.0,
    "extension": 2.0,
    "workspace": 3.0,
    "user": 4.0,
    "admin": 5.0,
}

# Shared-vocabulary mapping of the engine's decision verbs.
# ask_user -> prompt ; deny -> forbidden. unknown is emitted when no rule
# (custom or built-in) matches at all; never serialized as allow.
DECISION_MAP = {"allow": "allow", "ask_user": "prompt", "deny": "forbidden"}

# Chain separators the vendor documents as split-and-validate-per-part.
CHAIN_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;)\s*")

# Redirection operators: by default the engine "asks for confirmation when
# redirection is detected, even if a rule matches the command"
# (policy-engine reference, TOML rule schema -> allowRedirection).
REDIRECT_RE = re.compile(r"<<<|>>|<<|>|<")

SHELL_TOOL = "run_shell_command"


@dataclass
class Rule:
    tool_names: list
    command_prefixes: list
    command_regex: str | None
    args_pattern: str | None
    decision: str
    priority: int
    tier: str
    modes: list | None
    interactive: bool | None
    allow_redirection: bool
    source: str
    order: int

    @property
    def final_priority(self) -> float:
        return TIER_BASE[self.tier] + self.priority / 1000.0

    def describe(self) -> dict:
        return {
            "tier": self.tier,
            "final_priority": round(self.final_priority, 3),
            "decision": self.decision,
            "toolName": self.tool_names,
            "commandPrefix": self.command_prefixes or None,
            "commandRegex": self.command_regex,
            "argsPattern": self.args_pattern,
            "modes": self.modes,
            "interactive": self.interactive,
            "source": self.source,
        }


def load_policy(path: str, tier: str, _order_start: int = 0) -> list[Rule]:
    """Load one TOML policy file at the given tier."""
    with open(path, "rb") as fh:
        doc = tomllib.load(fh)
    rules: list[Rule] = []
    order = _order_start
    for raw in doc.get("rule", []):
        tool_name = raw.get("toolName", SHELL_TOOL)
        prefixes = raw.get("commandPrefix")
        regex = raw.get("commandRegex")
        args_pat = raw.get("argsPattern")
        if prefixes and regex:
            raise ValueError(
                f"{path}: cannot use commandPrefix and commandRegex in the same rule"
            )
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        modes = raw.get("modes")
        if isinstance(modes, str):
            modes = [modes]
        rules.append(
            Rule(
                tool_names=[tool_name] if isinstance(tool_name, str) else list(tool_name),
                command_prefixes=list(prefixes) if prefixes else [],
                command_regex=regex,
                args_pattern=args_pat,
                decision=raw["decision"],
                priority=int(raw.get("priority", 0)),
                tier=tier,
                modes=modes,
                interactive=raw.get("interactive"),
                allow_redirection=bool(raw.get("allowRedirection", False)),
                source=path,
                order=order,
            )
        )
        order += 1
    return rules


def default_tier_rules() -> list[Rule]:
    """Built-in Default-tier policies per the vendor "Default policies" section:
    - Write tools (like write_file, run_shell_command) default to ask_user.
    - In yolo mode, a high-priority rule allows all tools.
    These are loaded as the final fallback tier (final_priority ~1.xxx),
    below every custom tier.
    """
    return [
        Rule(
            tool_names=[SHELL_TOOL],
            command_prefixes=[],
            command_regex=None,
            args_pattern=None,
            decision="ask_user",
            priority=0,
            tier="default",
            modes=None,
            interactive=None,
            allow_redirection=False,
            source="<built-in default policies>",
            order=10**6,
        ),
        Rule(
            tool_names=["*"],
            command_prefixes=[],
            command_regex=None,
            args_pattern=None,
            decision="allow",
            priority=999,
            tier="default",
            modes=["yolo"],
            interactive=None,
            allow_redirection=False,
            source="<built-in default policies (yolo allow-all)>",
            order=10**6 + 1,
        ),
    ]


def tool_name_matches(pattern: str, called: str) -> bool:
    """toolName matching with the documented wildcards:
    * ; mcp_server_* ; mcp_*_toolName ; mcp_* ."""
    if pattern == "*":
        return True
    if "*" in pattern:
        return re.match("^" + re.escape(pattern).replace("\\*", ".*") + "$", called) is not None
    return pattern == called


def rule_matches(rule: Rule, tool: str, args_json: str, command: str,
                 mode: str, interactive: bool) -> bool:
    """All of the rule's conditions must hold for it to apply."""
    if not any(tool_name_matches(t, tool) for t in rule.tool_names):
        return False
    if rule.modes and mode not in rule.modes:
        return False
    if rule.interactive is not None and rule.interactive != interactive:
        return False
    if rule.command_prefixes:
        if not any(command.startswith(p) for p in rule.command_prefixes):
            return False
    if rule.command_regex:
        # Tested against the JSON representation of the arguments
        # (e.g. {"command":"git commit"}); unanchored search.
        if not re.search(rule.command_regex, args_json):
            return False
    if rule.args_pattern:
        if not re.search(rule.args_pattern, args_json):
            return False
    return True


def split_chain(command: str) -> list[str]:
    """Split a shell command on &&, ||, ; (NOT on |)."""
    parts = [p for p in CHAIN_SPLIT_RE.split(command) if p.strip()]
    return parts or [command]


def has_redirection(command: str) -> bool:
    return REDIRECT_RE.search(command) is not None


def decide_part(part: str, rules: list[Rule], mode: str, interactive: bool) -> dict:
    """Decide one chain part. Documented: highest final_priority wins;
    the first matching rule determines the outcome."""
    args_json = json.dumps({"command": part}, separators=(",", ":"))
    ordered = sorted(rules, key=lambda r: r.final_priority, reverse=True)
    for rule in ordered:
        if rule_matches(rule, SHELL_TOOL, args_json, part, mode, interactive):
            decision = rule.decision
            redirect_override = False
            if (
                has_redirection(part)
                and not rule.allow_redirection
                and decision == "allow"
            ):
                # Default: redirection asks for confirmation even when an
                # allow rule matched. (Deny is left as deny: the doc's
                # "asks for confirmation" cannot weaken a deny into a prompt;
                # recorded as an interpretation in TEST_LOG.md.)
                decision = "ask_user"
                redirect_override = True
            if decision == "ask_user" and not interactive:
                decision = "deny"
            return {
                "part": part,
                "decision": decision,
                "matched_rule": rule.describe(),
                "redirect_override": redirect_override,
                "headless_deny": decision == "deny" and rule.decision == "ask_user",
            }
    return {
        "part": part,
        "decision": "unknown",
        "matched_rule": None,
        "redirect_override": False,
        "headless_deny": False,
        "note": "no rules-layer decision (no custom or built-in rule matched)",
    }


def evaluate(argv: list[str], policies: list[tuple[str, str]],
             mode: str = "default", interactive: bool = True,
             include_defaults: bool = True) -> dict:
    """Deterministic T2 evaluation of argv through the documented TOML policy
    semantics. policies = [(toml_path, tier), ...] in load order (stable
    tie-break on equal final_priority)."""
    command = " ".join(argv)
    rules: list[Rule] = []
    order = 0
    for path, tier in policies:
        loaded = load_policy(path, tier, order)
        rules.extend(loaded)
        order += len(loaded)
    if include_defaults:
        rules.extend(default_tier_rules())

    parts = split_chain(command)
    part_results = [decide_part(p, rules, mode, interactive) for p in parts]

    # Whole-command decision. Documented: "If any part of the chain is
    # disallowed, the entire command is blocked." (deny wins; ask_user
    # propagates as confirmation-required; unknown propagates as unknown.)
    decisions = [p["decision"] for p in part_results]
    if "deny" in decisions:
        whole = "deny"
    elif "unknown" in decisions:
        whole = "unknown"
    elif "ask_user" in decisions:
        whole = "ask_user"
    else:
        whole = "allow"

    matched = [p["matched_rule"] for p in part_results if p["matched_rule"]]
    return {
        "argv": argv,
        "command": command,
        "mode": mode,
        "interactive": interactive,
        "parts": part_results,
        "engine_decision": whole,
        "decision": DECISION_MAP.get(whole, "unknown"),
        "matched_rules": matched,
    }


def engine_sha256() -> str:
    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------------------
# Fixture runner
# ---------------------------------------------------------------------------

RULES_MAP = {
    "fixtures/policies/default.rules": [("policy/baseline.toml", "user")],
    "fixtures/policies/protected_records.rules": [
        ("policy/protected_records.toml", "user")
    ],
}


def rules_for(fixture_rules: str) -> list[tuple[str, str]]:
    if fixture_rules in RULES_MAP:
        return RULES_MAP[fixture_rules]
    m = re.match(r"evidence/day1-baseline-2026-10-21/prec_([a-f])\.rules$", fixture_rules)
    if m:
        return [(f"policy/prec_{m.group(1)}.toml", "user")]
    raise ValueError(f"no TOML translation for rules file: {fixture_rules}")


def run_corpus(fixtures_path: str, shard: str, codex_native: dict) -> list[dict]:
    with open(fixtures_path) as fh:
        corpus = json.load(fh)
    out = []
    for f in corpus["fixtures"]:
        res = evaluate(f["argv"], rules_for(f["rules"]))
        codex = codex_native.get(f["id"])
        notes = []
        if not res["matched_rules"]:
            notes.append(
                "no custom-rule match; Default-tier built-in policy applies "
                "(run_shell_command defaults to ask_user -> confirmation dialog)"
            )
        elif any(
            r.get("source") == "<built-in default policies>"
            for r in res["matched_rules"]
        ):
            notes.append(
                "no custom-rule match; Default-tier built-in policy applies "
                "(run_shell_command defaults to ask_user -> confirmation dialog)"
            )
        if len(res["parts"]) > 1:
            notes.append(
                "chain split into %d parts; whole-command decision = most "
                "restrictive part (deny > unknown > ask_user > allow)"
                % len(res["parts"])
            )
        if f.get("resolve_host_executables"):
            notes.append(
                "CEILING: Gemini CLI has no host-executable resolution; "
                "commandPrefix matches the command STRING, so path-qualified "
                "forms never match bare prefixes (unlike Codex with "
                "resolve_host_executables=true)"
            )
        out.append(
            {
                "fixture_id": f["id"],
                "shard": shard,
                "argv": f["argv"],
                "evaluated_command": res["command"],
                "mode": res["mode"],
                "rules_source": f["rules"],
                "policy_files": [
                    {"path": p, "tier": t} for p, t in rules_for(f["rules"])
                ],
                "parts": res["parts"],
                "decision": res["decision"],
                "expected": f["expected"],
                "matches_expected": res["decision"] == f["expected"],
                "codex_t1": codex,
                "diverges_from_codex_t1": (codex is not None and codex != res["decision"]),
                "notes": "; ".join(notes),
            }
        )
    return out


def summarize(cases: list[dict]) -> dict:
    decisions: dict[str, int] = {}
    for c in cases:
        decisions[c["decision"]] = decisions.get(c["decision"], 0) + 1
    return {
        "count": len(cases),
        "decisions": decisions,
        "matches_expected": sum(1 for c in cases if c["matches_expected"]),
        "diverges_from_expected": sum(1 for c in cases if not c["matches_expected"]),
        "diverges_from_codex_t1": sum(1 for c in cases if c["diverges_from_codex_t1"]),
    }


def main() -> None:
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)
    repo = os.path.dirname(os.path.dirname(here))

    codex_native: dict[str, str] = {}
    native_path = os.path.join(
        repo, "evidence/day1-baseline-2026-10-21/native_results.json"
    )
    if os.path.exists(native_path):
        with open(native_path) as fh:
            for r in json.load(fh):
                try:
                    codex_native[r["fixture"]] = json.loads(r["stdout"]).get(
                        "decision", "unknown"
                    )
                except Exception:
                    codex_native[r["fixture"]] = "unknown"

    public = run_corpus(
        os.path.join(repo, "fixtures/corpus_public.json"), "public", codex_native
    )
    heldout = run_corpus(
        os.path.join(repo, "fixtures/corpus_heldout.json"), "heldout", codex_native
    )
    pa_public = run_corpus(
        os.path.join(repo, "fixtures/protected_records_public.json"),
        "public",
        codex_native,
    )
    pa_heldout = run_corpus(
        os.path.join(repo, "fixtures/protected_records_heldout.json"),
        "heldout",
        codex_native,
    )

    manifest = json.load(
        open(os.path.join(repo, "fixtures/corpus_manifest.json"))
    )
    pa_manifest = json.load(
        open(os.path.join(repo, "fixtures/protected_records_manifest.json"))
    )

    results = {
        "schema_version": "harness-results.v1",
        "harness": "gemini-cli",
        "version_under_test": "0.65.0",
        "version_sources": [
            "npm registry metadata: npm install @google/gemini-cli (2026-10-22) "
            "installed 0.65.0 (registry latest; same as prior pin)",
            "local read-only execution: node bundle/gemini.js --version -> 0.65.0",
        ],
        "route": "config-evaluation",
        "evidence_class": "T2-evaluation (never interrogated)",
        "engine_sha256": engine_sha256(),
        "corpus_version_hash": manifest["corpus_version_hash"],
        "debug_policy_verdict": (
            "refuted-at-pinned-version: the string 'debug-policy' is absent from "
            "the 0.65.0 bundle (full bundle grep, 2026-10-22); --help shows no "
            "check/evaluate subcommand. No native oracle exists."
        ),
        "public_cases": public,
        "public_protected_asset_cases": pa_public,
        "heldout_summary": {
            **summarize(heldout),
            "shard_sha256": manifest["held_out"]["sha256"],
        },
        "heldout_protected_asset_summary": {
            **summarize(pa_heldout),
            "shard_sha256": pa_manifest.get("held_out", {}).get("sha256"),
        },
    }
    with open("results.json", "w") as fh:
        json.dump(results, fh, indent=2)
        fh.write("\n")
    with open("results_heldout.local.json", "w") as fh:
        json.dump(
            {
                "schema_version": "harness-results.v1",
                "harness": "gemini-cli",
                "version_under_test": "0.65.0",
                "shard": "heldout",
                "shard_sha256": manifest["held_out"]["sha256"],
                "cases": heldout,
                "protected_asset_cases": pa_heldout,
            },
            fh,
            indent=2,
        )
        fh.write("\n")
    print(
        "wrote results.json (%d public cases, %d public PA cases); "
        "results_heldout.local.json (%d heldout cases, %d heldout PA cases)"
        % (len(public), len(pa_public), len(heldout), len(pa_heldout))
    )


if __name__ == "__main__":
    main()
