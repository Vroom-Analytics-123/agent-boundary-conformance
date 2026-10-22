#!/usr/bin/env python3
"""
Unit tests for the Claude Code T2 evaluation engine (evaluate.py).

Every wildcard-table row below is a WORKED EXAMPLE quoted from the official
Anthropic permissions documentation:
    https://code.claude.com/docs/en/permissions
    ("Wildcard patterns" table + "Match all uses of a tool" + "Use
    specifiers for fine-grained control" + "What a Bash rule doesn't match"
    + "Compound commands" + "Wrappers" sections, retrieved 2026-10-22,
    claude-code 2.1.307 docs).

Run:  python3 test_engine.py   (plain assert runner; exit 0 = all pass)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluate import (bash_rule_matches, evaluate, split_compound,
                      strip_wrappers, is_builtin_readonly)

DOC = "https://code.claude.com/docs/en/permissions"
passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL:", name)


def m(spec, cmd):
    """bash_rule_matches('...', '...') with the Bash(...) wrapper stripped."""
    return bash_rule_matches(spec, cmd)


# ---------------------------------------------------------------- wildcard
# table, docs section "Wildcard patterns":
# | You write | Matches | Doesn't match |
# ---------------------------------------------------------------------------

# Row: `Bash(npm run build)` | `npm run build` | `npm run build --watch`
check("exact rule matches the exact command", m("npm run build", "npm run build"))
check("exact rule does not match a longer command",
      not m("npm run build", "npm run build --watch"))

# Row: `Bash(npm run *)` | `npm run build`, `npm run test --watch`, `npm run`
#      | `npm install`
check("trailing wildcard matches subcommand", m("npm run *", "npm run build"))
check("trailing wildcard matches args", m("npm run *", "npm run test --watch"))
check("trailing wildcard matches the bare command", m("npm run *", "npm run"))
check("trailing wildcard does not match a different program",
      not m("npm run *", "npm install"))

# Row: `Bash(git log * main)` | `git log --oneline main`, `git log -5 main`,
#      `git log --output=<file> main` | `git log main`, `git push origin main`
check("middle wildcard: --oneline", m("git log * main", "git log --oneline main"))
check("middle wildcard: -5", m("git log * main", "git log -5 main"))
check("middle wildcard: --output=<file>",
      m("git log * main", "git log --output=<file> main"))
check("middle wildcard needs text in its place (no bare 'git log main')",
      not m("git log * main", "git log main"))
check("middle wildcard: different subcommand",
      not m("git log * main", "git push origin main"))

# Row: `Bash(git * main)` | `git merge main`, `git push origin main`,
#      `git -c core.fsmonitor=<script> diff main` | `git log`
check("early wildcard: merge", m("git * main", "git merge main"))
check("early wildcard: push origin", m("git * main", "git push origin main"))
check("early wildcard covers -c program execution",
      m("git * main", "git -c core.fsmonitor=<script> diff main"))
check("early wildcard: no 'main' arg", not m("git * main", "git log"))

# Row: `Bash(* --version)` | `node --version`, `bash -c 'echo hi' --version`
#      | `node -v`
check("leading wildcard: node", m("* --version", "node --version"))
check("leading wildcard across a compound string",
      m("* --version", "bash -c 'echo hi' --version"))
check("leading wildcard: --version only", not m("* --version", "node -v"))

# Row: `Bash(ls *)` | `ls -la`, `ls` | `lsof`
check("space-star matches args", m("ls *", "ls -la"))
check("space-star matches the bare command (only-wildcard concession)",
      m("ls *", "ls"))
check("space-star does not match lsof", not m("ls *", "lsof"))

# Row: `Bash(ls*)` | `ls -la`, `lsof` |
check("no-space star matches lsof", m("ls*", "lsof"))
check("no-space star matches args", m("ls*", "ls -la"))
check("no-space star matches bare ls (glob, not concession)", m("ls*", "ls"))

# Row: `Bash(* --help *)` | `npm --help x` | `npm --help`
check("two wildcards: with trailing text", m("* --help *", "npm --help x"))
check("two wildcards: no bare-command concession",
      not m("* --help *", "npm --help"))

# Docs: "The `:*` suffix is an equivalent way to write a trailing wildcard,
# so `Bash(ls:*)` matches the same commands as `Bash(ls *)`."
check("colon-star == space-star (ls)", m("ls:*", "ls"))
check("colon-star == space-star (ls -la)", m("ls:*", "ls -la"))
check("colon-star == space-star (not lsof)", not m("ls:*", "lsof"))

# Docs: "In a pattern like `Bash(git:* push)`, the colon is treated as a
# literal character" (only recognised at the END of a pattern).
check("colon mid-pattern is literal",
      m("git:* push", "git:* push") and not m("git:* push", "git push"))

# ---------------------------------------------------------------- bare tool
# names, docs "Match all uses of a tool":
# `Bash` | Matches all Bash commands. `Bash(*)` is equivalent to `Bash`.
# ---------------------------------------------------------------------------
check("bare Bash matches everything", m("*", "rm -rf /"))
check("empty specifier matches everything", m("", "anything at all"))

# ------------------------------------------------- "What a Bash rule
# doesn't match" table: a deny/ask rule covers the invocation Claude usually
# produces and isn't a security boundary around the program.
# ---------------------------------------------------------------------------
check("curl rule stops bare curl",
      m("curl *", "curl https://example.com"))
check("curl rule does not stop /usr/bin/curl",
      not m("curl *", "/usr/bin/curl https://example.com"))
check("curl rule does not stop sh -c wrapper",
      not m("curl *", "sh -c 'curl https://example.com'"))
check("rm rule stops rm -rf build/", m("rm *", "rm -rf build/"))
check("rm rule does not stop /bin/rm", not m("rm *", "/bin/rm -rf build/"))
check("rm rule does not stop bash -c wrapper",
      not m("rm *", "bash -c 'rm -rf build/'"))
check("git push rule stops plain push", m("git push *", "git push origin main"))
check("git push rule does not stop git -C . push",
      not m("git push *", "git -C . push origin main"))
check("git push rule does not stop git -c push.default push",
      not m("git push *", "git -c push.default=current push origin main"))
check("git push rule does not stop quoted subcommand",
      not m("git push *", "git 'push' origin main"))

# ------------------------------------------------------------- compound
# commands: "Deny and ask rules apply when any subcommand matches them"
# ---------------------------------------------------------------------------
POL = {"allow": [], "ask": [], "deny": ["Bash(rm *)"]}
r = evaluate("cd /tmp && rm -rf x", POL)
check("deny applies to a && subcommand", r["decision"] == "forbidden")
r = evaluate('echo "$(rm -rf x)"', POL)
check("deny applies inside command substitution", r["decision"] == "forbidden")
r = evaluate("rm -rf x || true", POL)
check("deny applies to a || subcommand", r["decision"] == "forbidden")
r = evaluate("rm -rf x; echo done", POL)
check("deny applies to a ;-separated subcommand", r["decision"] == "forbidden")

# "When `&&` or `||` has nothing after it, such as in `npm test &&`,
# Claude Code treats the command as unparseable" -> our splitter yields one
# subcommand `npm test`; no trailing empty part is evaluated.
check("trailing && leaves a single subcommand",
      split_compound("npm test &&") == ["npm test"])
check("pipe splits into subcommands",
      split_compound("git status | rm -rf x") == ["git status", "rm -rf x"])
check("quotes protect separators",
      split_compound("echo 'a && b' && true") == ["echo 'a && b'", "true"])

# ------------------------------------------------------------------ wrappers
# "Before matching Bash rules, Claude Code strips a fixed set of wrappers"
# ---------------------------------------------------------------------------
check("timeout stripped with duration",
      strip_wrappers("timeout 30 npm test", False) == "npm test")
check("time stripped", strip_wrappers("time npm test", False) == "npm test")
check("nice stripped", strip_wrappers("nice npm test", False) == "npm test")
check("nohup stripped", strip_wrappers("nohup npm test", False) == "npm test")
check("stdbuf stripped", strip_wrappers("stdbuf npm test", False) == "npm test")
check("command stripped", strip_wrappers("command rm -rf x", False) == "rm -rf x")
check("builtin stripped", strip_wrappers("builtin cd /tmp", False) == "cd /tmp")
check("noglob stripped", strip_wrappers("noglob npm test", False) == "npm test")
check("command -v query form NOT stripped",
      strip_wrappers("command -v rm", False) == "command -v rm")
check("bare xargs stripped", strip_wrappers("xargs grep p", False) == "grep p")
check("xargs with flags NOT stripped",
      strip_wrappers("xargs -n1 grep p", False) == "xargs -n1 grep p")
check("env NOT stripped", strip_wrappers("env rm -rf x", False) == "env rm -rf x")
check("sudo NOT stripped", strip_wrappers("sudo rm -rf x", False) == "sudo rm -rf x")
check("deny matches past any leading assignment",
      strip_wrappers("FOO=bar rm -rf tmp/", False) == "rm -rf tmp/")
check("allow matches past NODE_ENV assignment",
      strip_wrappers("NODE_ENV=test npm test", True) == "npm test")
check("allow does NOT match past other assignments",
      strip_wrappers("FOO=bar npm test", True) == "FOO=bar npm test")

# Wrapper stripping end-to-end: docs example "`Bash(npm test *)` also
# matches `timeout 30 npm test`".
r = evaluate("timeout 30 npm test", {"allow": ["Bash(npm test *)"],
                                             "ask": [], "deny": []})
check("allow matches through timeout wrapper", r["decision"] == "allow")
r = evaluate("xargs rm -rf", {"allow": [], "ask": [],
                              "deny": ["Bash(rm -rf *)"]})
check("deny matches through bare xargs", r["decision"] == "forbidden")

# --------------------------------------------------------------- precedence
# "Rules are evaluated in order: deny, then ask, then allow. The first match
# in that order determines the outcome, and rule specificity doesn't change
# the order." + worked example: "A broad deny rule like `Bash(aws *)`
# blocks every matching call, including calls that also match a narrower
# allow rule like `Bash(aws s3 ls)`."
# ---------------------------------------------------------------------------
r = evaluate("aws s3 ls", {"allow": ["Bash(aws s3 ls)"], "ask": [],
                           "deny": ["Bash(aws *)"]})
check("broad deny beats narrower allow", r["decision"] == "forbidden")
r = evaluate("git push origin main",
             {"allow": ["Bash(git push origin main)"], "ask": ["Bash(git push *)"],
              "deny": []})
check("ask beats narrower allow (docs example class)",
      r["decision"] == "prompt")
# both orders, conflicting deny/ask/allow: deny always wins
r = evaluate("git status",
             {"allow": ["Bash(git status *)"], "ask": ["Bash(git *)"],
              "deny": ["Bash(git *)"]})
check("deny wins regardless of list position", r["decision"] == "forbidden")
r = evaluate("git status",
             {"allow": ["Bash(git *)"], "ask": ["Bash(git status *)"],
              "deny": []})
check("ask wins over allow even when allow is broader",
      r["decision"] == "prompt")
r = evaluate("git status",
             {"allow": ["Bash(git *)"], "ask": [],
              "deny": []})
check("allow applies when nothing higher matches",
      r["decision"] == "allow")

# ------------------------------------------------------------- no-match
# default: no rule match -> the harness would prompt the user; the shared
# vocabulary serializes this as unknown with layer attribution, never allow.
# ---------------------------------------------------------------------------
r = evaluate("frobnicate --force", {"allow": [], "ask": [], "deny": []})
check("no-match is unknown, never allow", r["decision"] == "unknown")
check("no-match carries layer attribution",
      "layer attribution" in r["note"] or "no rules-layer decision" in r["note"])
r = evaluate("curl https://example.com",
             {"allow": ["Bash(git status *)"], "ask": [], "deny": []})
check("unmatched curl is unknown", r["decision"] == "unknown")

# ------------------------------------------------------- built-in read-only
# set: "Claude Code recognizes a built-in set of Bash commands as read-only
# and runs them without a permission prompt in every mode". The set includes
# ls, cat, echo, pwd, head, tail, grep, find, wc, which, diff, stat, du, cd,
# and read-only forms of git.
# ---------------------------------------------------------------------------
check("ls is builtin read-only", is_builtin_readonly("ls -la"))
check("git log is builtin read-only", is_builtin_readonly("git log --oneline"))
check("git status is builtin read-only", is_builtin_readonly("git status"))
check("git push is NOT read-only", not is_builtin_readonly("git push"))
check("rm is NOT read-only", not is_builtin_readonly("rm -rf /tmp/x"))
check("find with -delete is NOT read-only",
      not is_builtin_readonly("find . -name x -delete"))
check("unquoted glob is NOT read-only",
      not is_builtin_readonly("ls *.ts"))
r = evaluate("git log", {"allow": [], "ask": [], "deny": []})
check("git log allowed via builtin read-only (not a rules-layer decision)",
      r["decision"] == "allow" and "built-in read-only" in r["note"])
# compound: every part must qualify on its own
r = evaluate("cd /tmp && ls", {"allow": [], "ask": [], "deny": []})
check("cd /tmp && ls runs without a prompt", r["decision"] == "allow")
r = evaluate("git status && frobnicate", {"allow": [], "ask": [], "deny": []})
check("compound with an uncovered part is unknown",
      r["decision"] == "unknown")

print("DOC:", DOC)
print("passed=%d failed=%d" % (passed, failed))
sys.exit(1 if failed else 0)
