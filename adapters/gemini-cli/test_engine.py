#!/usr/bin/env python3
"""Unit tests for evaluate.py — the Gemini CLI TOML policy-engine reimplementation.

Every test covers a WORKED EXAMPLE from the vendor's own documentation, cited
as URL + section. Tests are labelled T2-evaluated (never interrogated): they
verify the reimplementation against documented semantics, not the vendor binary.

Primary sources (retrieved 2026-10-22):
  PE  = https://geminicli.com/docs/reference/policy-engine
  SH  = https://geminicli.com/docs/tools/shell/
  CFG = https://geminicli.com/docs/reference/configuration/
  PLN = https://geminicli.com/docs/cli/plan-mode/
  YB  = https://allen.hutchison.org/2025/11/26/the-guardrails-of-autonomy/ (policy-engine worked examples)

Pinned harness: @google/gemini-cli@0.65.0.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate
from evaluate import evaluate as ev, load_policy, default_tier_rules, engine_sha256

PASS = []
FAIL = []


def _toml_policies(toml_text: str, tier: str = "user"):
    fh = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
    fh.write(toml_text)
    fh.close()
    return [(fh.name, tier)]


def check(name: str, fn, cite: str):
    try:
        fn()
        PASS.append(name)
        print(f"PASS {name}  [{cite}]")
    except AssertionError as e:
        FAIL.append((name, str(e)))
        print(f"FAIL {name}: {e}  [{cite}]")


# ---------------------------------------------------------------- PE §Quick start
def t_quickstart_deny_prefix():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "rm -rf"
decision = "deny"
priority = 100
''')
    r = ev(["rm", "-rf", "/"], pol)
    assert r["decision"] == "forbidden", r

check("quickstart: rm -rf prefix -> deny",
      t_quickstart_deny_prefix, "PE §Quick start")

# ---------------------------------------------------------------- PE §Core concepts
def t_core_concepts_git_ask():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "ask_user"
priority = 100
''')
    r = ev(["git", "status"], pol)
    assert r["decision"] == "prompt", r

check("core-concepts: any git command -> ask_user",
      t_core_concepts_git_ask, "PE §Core concepts")

# ------------------------------------------------ PE §Priority system and tiers
def t_higher_priority_wins():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "deny"
priority = 100
[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "allow"
priority = 999
''')
    r = ev(["git", "status"], pol)
    assert r["decision"] == "allow", r

check("priority: higher number wins within a tier",
      t_higher_priority_wins, "PE §Priority system and tiers")

def t_admin_beats_user_despite_lower_priority():
    # Worked example on the page: user priority 100 -> 3.100, admin priority
    # 20 -> 4.020, admin wins.
    admin = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "deny"
priority = 20
''', tier="admin")
    user = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "allow"
priority = 100
''', tier="user")
    r = ev(["git", "status"], admin + user)
    assert r["decision"] == "forbidden", r
    assert r["parts"][0]["matched_rule"]["tier"] == "admin", r

check("tiers: admin p20 beats user p100 (doc worked example)",
      t_admin_beats_user_despite_lower_priority, "PE §Priority system and tiers")

def t_tier_dominates_priority():
    user = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "allow"
priority = 999
''', tier="user")
    default_deny = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "deny"
priority = 999
''', tier="default")
    r = ev(["git", "status"], user + default_deny)
    assert r["decision"] == "allow", r

check("tiers: user p999 beats default p999",
      t_tier_dominates_priority, "PE §Priority system and tiers")

# ------------------------------------- PE §Special syntax for run_shell_command
def t_command_regex_example():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandRegex = "git (commit|push)"
decision = "ask_user"
priority = 100
''')
    r = ev(["git", "commit", "-m", "x"], pol)
    assert r["decision"] == "prompt", r
    r2 = ev(["git", "status"], pol)
    assert r2["decision"] == "prompt", r2  # default-tier fallback, no custom match
    assert r2["parts"][0]["matched_rule"]["source"] == "<built-in default policies>", r2

check("commandRegex 'git (commit|push)' matches git commit",
      t_command_regex_example, "PE §Special syntax for run_shell_command")

# ------------------------------------------------------ PE §TOML rule schema
def t_args_pattern_example():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
argsPattern = '"command":"(git|npm)'
decision = "allow"
priority = 100
''')
    r = ev(["npm", "test"], pol)
    assert r["decision"] == "allow", r

check("argsPattern doc example allows npm test",
      t_args_pattern_example, "PE §TOML rule schema")

def t_interactive_false_headless_only():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "npm test"
decision = "allow"
priority = 100
interactive = false
''')
    r_head = ev(["npm", "test"], pol, interactive=False)
    assert r_head["decision"] == "allow", r_head
    r_int = ev(["npm", "test"], pol, interactive=True)
    assert r_int["decision"] == "prompt", r_int  # rule inactive interactively

check("interactive=false applies only in headless mode",
      t_interactive_false_headless_only, "PE §Execution environment")

def t_ask_user_is_deny_when_headless():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "ask_user"
priority = 100
''')
    r = ev(["git", "status"], pol, interactive=False)
    assert r["engine_decision"] == "deny", r
    assert r["decision"] == "forbidden", r

check("ask_user treated as deny in non-interactive mode",
      t_ask_user_is_deny_when_headless, "PE §Decisions")

def t_modes_absent_always_active():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git status"
decision = "allow"
priority = 100
''')
    for mode in ("default", "autoEdit", "plan", "yolo"):
        r = ev(["git", "status"], pol, mode=mode)
        # yolo mode adds the built-in yolo allow-all at default tier (1.999),
        # but the user-tier rule (4.100) still wins -> allow either way.
        assert r["decision"] == "allow", (mode, r)

check("rule with no modes is always active (all modes)",
      t_modes_absent_always_active, "PLN §Custom policies")

def t_modes_yolo_scoped():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "docker"
decision = "deny"
priority = 999
modes = ["yolo"]
''')
    r_default = ev(["docker", "ps"], pol, mode="default")
    assert r_default["decision"] == "prompt", r_default  # inactive; default fallback
    r_yolo = ev(["docker", "ps"], pol, mode="yolo")
    assert r_yolo["decision"] == "forbidden", r_yolo

check("modes=['yolo'] re-imposes deny inside YOLO",
      t_modes_yolo_scoped, "YB §Yolo Mode + CFG general.defaultApprovalMode")

def t_command_prefix_array():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = ["npm test", "git diff"]
decision = "allow"
priority = 100
''')
    assert ev(["npm", "test"], pol)["decision"] == "allow"
    assert ev(["git", "diff"], pol)["decision"] == "allow"
    assert ev(["npm", "install"], pol)["decision"] == "prompt"

check("commandPrefix array form",
      t_command_prefix_array, "substack policy example via manifest")

def t_toolname_wildcard():
    pol = _toml_policies('''[[rule]]
toolName = "*"
decision = "ask_user"
priority = 10
''')
    r = ev(["git", "status"], pol)
    assert r["decision"] == "prompt", r

check("toolName='*' matches any tool",
      t_toolname_wildcard, "PE §Tool Name")

def t_redirection_default_asks():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "echo"
decision = "allow"
priority = 100
''')
    r = ev(["echo", "hi", ">", "out.txt"], pol)
    assert r["decision"] == "prompt", r
    assert r["parts"][0]["redirect_override"] is True, r

check("redirection forces confirmation even when allow matched",
      t_redirection_default_asks, "PE §TOML rule schema (allowRedirection)")

def t_redirection_allowed_when_permitted():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "echo"
decision = "allow"
priority = 100
allowRedirection = true
''')
    r = ev(["echo", "hi", ">", "out.txt"], pol)
    assert r["decision"] == "allow", r

check("allowRedirection=true permits redirection",
      t_redirection_allowed_when_permitted, "PE §TOML rule schema (allowRedirection)")

def t_prefix_and_regex_together_rejected():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
commandRegex = "git"
decision = "allow"
priority = 100
''')
    try:
        evaluate.rules_for  # touch module
        ev(["git"], pol)
    except ValueError:
        return
    raise AssertionError("expected ValueError for prefix+regex in one rule")

check("commandPrefix+commandRegex in one rule is rejected",
      t_prefix_and_regex_together_rejected,
      "PE §TOML rule schema ('You cannot use commandPrefix and commandRegex in the same rule')")

# ------------------------------------------------------ PE §Default policies
def t_no_match_falls_back_to_ask_user():
    r = ev(["frobnicate", "--force"], [])
    assert r["decision"] == "prompt", r
    assert r["parts"][0]["matched_rule"]["source"] == "<built-in default policies>", r

check("no custom match -> default-tier ask_user (confirmation dialog)",
      t_no_match_falls_back_to_ask_user, "PE §Default policies")

def t_yolo_builtin_allow_all_vs_user_deny():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "rm -rf"
decision = "deny"
priority = 999
''')
    r = ev(["rm", "-rf", "/tmp/x"], pol, mode="yolo")
    assert r["decision"] == "forbidden", r
    assert r["parts"][0]["matched_rule"]["tier"] == "user", r

check("yolo: user-tier deny (4.999) beats built-in yolo allow-all (1.999)",
      t_yolo_builtin_allow_all_vs_user_deny, "PE §Default policies")

def t_yolo_no_user_rules_allows():
    r = ev(["ls", "-la"], [], mode="yolo")
    assert r["decision"] == "allow", r
    assert r["parts"][0]["matched_rule"]["modes"] == ["yolo"], r

check("yolo: built-in high-priority allow-all applies with no user rules",
      t_yolo_no_user_rules_allows, "PE §Default policies")

def t_chained_redirection_each_part():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "make"
decision = "allow"
priority = 100
allowRedirection = true
[[rule]]
toolName = "run_shell_command"
commandPrefix = "echo"
decision = "allow"
priority = 100
''')
    r = ev(["make", "build", ">", "log.txt", "&&", "echo", "done"], pol)
    assert r["decision"] == "allow", r

check("chained: each part needs its own redirection permission",
      t_chained_redirection_each_part, "PE §TOML rule schema (allowRedirection)")

# ------------------------------------------------------ SH §Command restrictions
HERE = os.path.dirname(os.path.abspath(__file__))

def _baseline():
    return [(os.path.join(HERE, "policy", "baseline.toml"), "user")]

def t_chain_split_deny_part_blocks_all():
    r = ev(["git", "status", "&&", "rm", "-rf", "/tmp/x"], _baseline())
    assert len(r["parts"]) == 2, r
    assert r["parts"][0]["decision"] == "allow", r
    assert r["parts"][1]["decision"] == "deny", r
    assert r["decision"] == "forbidden", r

check("chain &&: disallowed part blocks the whole command",
      t_chain_split_deny_part_blocks_all, "SH §Command restrictions (1)")

def t_chain_split_or_and_semi():
    r1 = ev(["git", "status", "||", "rm", "-rf", "/tmp/x"], _baseline())
    assert r1["decision"] == "forbidden", r1
    r2 = ev(["git", "status", ";", "rm", "-rf", "/tmp/x"], _baseline())
    assert r2["decision"] == "forbidden", r2

check("chain || and ; also split and validate per part",
      t_chain_split_or_and_semi, "SH §Command restrictions (1)")

def t_prefix_matching():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git"
decision = "allow"
priority = 100
''')
    assert ev(["git", "status"], pol)["decision"] == "allow"
    assert ev(["git", "log"], pol)["decision"] == "allow"

check("prefix matching: allow 'git' covers 'git status' and 'git log'",
      t_prefix_matching, "SH §Command restrictions (2)")

def t_pipe_not_split():
    # Only &&, ||, ; split. A pipe keeps one command; the "git status" prefix
    # matches the whole string.
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "git status"
decision = "allow"
priority = 100
''')
    r = ev(["git", "status", "|", "head"], pol)
    assert len(r["parts"]) == 1, r
    assert r["decision"] == "allow", r

check("pipe | does not split the command (only &&, ||, ;)",
      t_pipe_not_split, "SH §Command restrictions (1)")

def t_blocklist_precedence_via_priority():
    pol = _toml_policies('''[[rule]]
toolName = "run_shell_command"
commandPrefix = "rm"
decision = "deny"
priority = 999
[[rule]]
toolName = "run_shell_command"
commandPrefix = "rm"
decision = "allow"
priority = 100
''')
    r = ev(["rm", "-rf", "/"], pol)
    assert r["decision"] == "forbidden", r

check("blocklist precedence: deny p999 beats allow p100",
      t_blocklist_precedence_via_priority, "SH §Command restrictions (3)")

# -------------------------------- Corpus precedence probes (policy/prec_*.toml)
def _prec(letter):
    return [(os.path.join(HERE, "policy", f"prec_{letter}.toml"), "user")]

def t_prec_a():
    r = ev(["git", "status"], _prec("a"))
    assert r["decision"] == "prompt", r  # tie -> file order -> [git] ask_user first

def t_prec_b():
    r = ev(["git", "status"], _prec("b"))
    assert r["decision"] == "allow", r  # tie -> file order -> allow first

def t_prec_c():
    r = ev(["git", "status"], _prec("c"))
    assert r["decision"] == "allow", r  # identical prefix, tie -> first wins

def t_prec_d():
    r = ev(["git", "status"], _prec("d"))
    assert r["decision"] == "forbidden", r

def t_prec_e():
    r = ev(["rm", "-rf", "/tmp/x"], _prec("e"))
    assert r["decision"] == "prompt", r  # broader ask_user first

def t_prec_f():
    r = ev(["rm", "-rf", "/tmp/x"], _prec("f"))
    assert r["decision"] == "forbidden", r

for letter, name, cite in [
    ("a", "prec_a: [git]ask before [git,status]allow -> prompt", "prec_a.rules (committed probe input)"),
    ("b", "prec_b: reversed order -> allow (order-dependent)", "prec_b.rules (committed probe input)"),
    ("c", "prec_c: identical prefix allow/deny -> allow (first wins)", "prec_c.rules (committed probe input)"),
    ("d", "prec_d: deny then allow -> forbidden", "prec_d.rules (committed probe input)"),
    ("e", "prec_e: broader ask before narrower deny -> prompt", "prec_e.rules (committed probe input)"),
    ("f", "prec_f: narrower deny first -> forbidden", "prec_f.rules (committed probe input)"),
]:
    check(name, {"a": t_prec_a, "b": t_prec_b, "c": t_prec_c,
                 "d": t_prec_d, "e": t_prec_e, "f": t_prec_f}[letter],
          cite)

# ------------------------------------------------- engine-level properties
def t_deterministic():
    pol = _baseline()
    a = json.dumps(ev(["rm", "-rf", "/tmp/x", "&&", "git", "status"], pol), sort_keys=True)
    b = json.dumps(ev(["rm", "-rf", "/tmp/x", "&&", "git", "status"], pol), sort_keys=True)
    assert a == b and len(a) > 0

check("determinism: same input twice -> byte-identical output",
      t_deterministic, "wave requirement (route (a) determinism bar, applied to (b))")

def t_engine_sha_stable():
    h1 = engine_sha256()
    h2 = engine_sha256()
    assert h1 == h2 and len(h1) == 64

check("engine_sha256 is stable and 64 hex chars",
      t_engine_sha_stable, "results.json schema")

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)
