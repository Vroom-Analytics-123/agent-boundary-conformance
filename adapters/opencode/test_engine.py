#!/usr/bin/env python3
"""Unit tests for the OpenCode 1.x T2 evaluation engine.

Every test cites the worked example / statement in the official vendor doc:
  DOC = https://opencode.ai/docs/permissions (retrieved 2026-10-22)
Sections are quoted verbatim from that page.

Run: python3 test_engine.py  (all tests must pass; no network, no CLI)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import evaluate as E

DOC = "https://opencode.ai/docs/permissions"

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print("PASS  %s" % name)
    else:
        print("FAIL  %s  %s" % (name, detail))
        FAILURES.append(name)


def ev(permission, tool, command, home="/home/testuser", agent_permission=None):
    return E.evaluate_permission(permission, tool, command,
                                 home=home, agent_permission=agent_permission)


# --------------------------------------------------------------------------
# T01 — decision verbs. DOC §"Each permission rule resolves to one of":
#   "allow" — run without approval / "ask" — prompt for approval /
#   "deny" — block the action
# --------------------------------------------------------------------------
check("T01 verbs map to shared vocabulary",
      ev("allow", "shell", "anything").decision == "allow"
      and ev("ask", "shell", "anything").decision == "prompt"
      and ev("deny", "shell", "anything").decision == "forbidden",
      "DOC §'Each permission rule resolves to one of'")

# --------------------------------------------------------------------------
# T02 — "You can set all permissions at once": { "permission": "allow" }
# --------------------------------------------------------------------------
check("T02 global verb applies to every tool",
      ev("allow", "shell", "rm -rf /").decision == "allow"
      and ev("allow", "webfetch", "https://x.example/").decision == "allow",
      "DOC §'You can set all permissions at once'")

# --------------------------------------------------------------------------
# T03 — global + per-tool override. DOC example:
#   { "permission": { "*": "ask", "shell": "allow", "edit": "deny" } }
# --------------------------------------------------------------------------
p = {"*": "ask", "shell": "allow", "edit": "deny"}
check("T03 global/tool override: shell->allow edit->deny read->ask(via *)",
      ev(p, "shell", "git status").decision == "allow"
      and ev(p, "edit", "README.md").decision == "forbidden"
      and ev(p, "read", "README.md").decision == "prompt",
      "DOC §'You can set permissions globally (with *)'")

# --------------------------------------------------------------------------
# T04 — the canonical pattern-object worked example. DOC:
#   "shell": { "*": "ask", "git *": "allow", "npm *": "allow",
#              "rm *": "deny", "grep *": "allow" }
#   "Rules are evaluated by pattern match, with the last matching rule
#    winning."
# --------------------------------------------------------------------------
shell_doc = {"*": "ask", "git *": "allow", "npm *": "allow",
             "rm *": "deny", "grep *": "allow"}
check("T04a doc example: 'git status' -> allow (last match beats catch-all)",
      ev({"shell": shell_doc}, "shell", "git status").decision == "allow")
check("T04b doc example: 'npm test' -> allow",
      ev({"shell": shell_doc}, "shell", "npm test").decision == "allow")
check("T04c doc example: 'rm -rf /' -> deny",
      ev({"shell": shell_doc}, "shell", "rm -rf /").decision == "forbidden")
check("T04d doc example: 'grep -r foo' -> allow",
      ev({"shell": shell_doc}, "shell", "grep -r foo").decision == "allow")
check("T04e doc example: 'ls -la' -> ask (only catch-all matches)",
      ev({"shell": shell_doc}, "shell", "ls -la").decision == "prompt")
# literal-space subtlety: "git *" requires the space, so bare "git" matches
# only the catch-all.
check("T04f doc example: bare 'git' does not match 'git *' (space is literal)",
      ev({"shell": shell_doc}, "shell", "git").decision == "prompt")
r = ev({"shell": shell_doc}, "shell", "git status")
check("T04g matched-rule index records order of matches",
      r.matched == [(0, "*", "ask"), (1, "git *", "allow")],
      "got %r" % (r.matched,))

# --------------------------------------------------------------------------
# T05 — order swap flips the verdict: LAST match wins, not first.
# --------------------------------------------------------------------------
swapped = dict(reversed(list(shell_doc.items())))
check("T05 reversed order: 'git status' -> ask (catch-all now last)",
      ev({"shell": swapped}, "shell", "git status").decision == "prompt"
      and ev({"shell": swapped}, "shell", "rm -rf /").decision == "prompt",
      "DOC §'Rules are evaluated by pattern match, with the last matching rule winning'")

# --------------------------------------------------------------------------
# T06 — wildcard table. DOC: "* matches zero or more of any character",
# "? matches exactly one character", "All other characters match literally"
# --------------------------------------------------------------------------
check("T06a '*' matches zero chars: 'git*' matches 'git'",
      E.pattern_matches("git*", "git", "/h"))
check("T06b '*' matches many chars: 'git*' matches 'git status --porcelain'",
      E.pattern_matches("git*", "git status --porcelain", "/h"))
check("T06c '?' matches exactly one: 'git statu?' matches 'git status'",
      E.pattern_matches("git statu?", "git status", "/h"))
check("T06d '?' does not match zero: 'git statu?' misses 'git statu'",
      not E.pattern_matches("git statu?", "git statu", "/h"))
check("T06e '?' does not match two: 'git statu?' misses 'git statusx'",
      not E.pattern_matches("git statu?", "git statusx", "/h"))
check("T06f literal chars: 'git.status' misses 'gitXstatus'",
      not E.pattern_matches("git.status", "gitXstatus", "/h")
      and E.pattern_matches("git.status", "git.status", "/h"))

# --------------------------------------------------------------------------
# T07 — home expansion. DOC:
#   "~/projects/* -> /Users/username/projects/*",
#   "$HOME/projects/* -> /Users/username/projects/*", "~ -> /Users/username"
# --------------------------------------------------------------------------
check("T07a '~/projects/*' expands at pattern start",
      E.pattern_matches("~/projects/*", "/Users/u/projects/a", "/Users/u")
      and not E.pattern_matches("~/projects/*", "/other/projects/a", "/Users/u"),
      "DOC §home expansion")
check("T07b '$HOME/projects/*' expands at pattern start",
      E.pattern_matches("$HOME/projects/*", "/Users/u/projects/a", "/Users/u"),
      "DOC §home expansion")
check("T07c no expansion mid-pattern: 'x~/y' is literal",
      E.pattern_matches("x~/y", "x~/y", "/Users/u")
      and not E.pattern_matches("x~/y", "x/Users/u/y", "/Users/u"),
      "DOC §'at the start of a pattern'")

# --------------------------------------------------------------------------
# T08 — the read/.env defaults worked example. DOC §"If you don't specify
# anything ... 'read' is 'allow', but '.env' files are denied by default":
#   "read": { "*": "allow", "*.env": "deny", "*.env.*": "deny",
#             "*.env.example": "allow" }
# The money case: .env.example ends deny-then-allow -> allow.
# --------------------------------------------------------------------------
read_env = {"*": "allow", "*.env": "deny", "*.env.*": "deny",
            "*.env.example": "allow"}
check("T08a doc .env example: '.env' -> deny",
      ev({"read": read_env}, "read", ".env").decision == "forbidden")
check("T08b doc .env example: '.env.local' -> deny",
      ev({"read": read_env}, "read", ".env.local").decision == "forbidden")
check("T08c doc .env example: '.env.example' -> allow (later allow beats deny)",
      ev({"read": read_env}, "read", ".env.example").decision == "allow")
check("T08d doc .env example: 'src/index.ts' -> allow",
      ev({"read": read_env}, "read", "src/index.ts").decision == "allow")

# --------------------------------------------------------------------------
# T09 — the edit worked example. DOC:
#   "edit": { "*": "deny", "packages/web/src/content/docs/*.mdx": "allow" }
# --------------------------------------------------------------------------
edit_doc = {"*": "deny", "packages/web/src/content/docs/*.mdx": "allow"}
check("T09a doc edit example: docs mdx -> allow",
      ev({"edit": edit_doc}, "edit", "packages/web/src/content/docs/a.mdx").decision == "allow")
check("T09b doc edit example: other file -> deny",
      ev({"edit": edit_doc}, "edit", "notes.md").decision == "forbidden")

# --------------------------------------------------------------------------
# T10 — the webfetch worked example. DOC:
#   "webfetch": { "*": "ask", "https://en.wikipedia.org/*": "allow" }
# --------------------------------------------------------------------------
wf_doc = {"*": "ask", "https://en.wikipedia.org/*": "allow"}
check("T10 doc webfetch example",
      ev({"webfetch": wf_doc}, "webfetch", "https://en.wikipedia.org/wiki/X").decision == "allow"
      and ev({"webfetch": wf_doc}, "webfetch", "https://example.com/").decision == "prompt")

# --------------------------------------------------------------------------
# T11 — external_directory worked example. DOC:
#   "external_directory": { "~/projects/personal/**": "allow" } and
#   "edit": { "~/projects/personal/**": "deny" }
# ("**" is two zero-or-more wildcards; matches nested paths.)
# --------------------------------------------------------------------------
ext_doc = {"external_directory": {"~/projects/personal/**": "allow"},
           "edit": {"~/projects/personal/**": "deny"}}
check("T11 doc external_directory example",
      ev(ext_doc, "external_directory",
         "/Users/u/projects/personal/a/b", home="/Users/u").decision == "allow"
      and ev(ext_doc, "edit",
             "/Users/u/projects/personal/a.md", home="/Users/u").decision == "forbidden")

# --------------------------------------------------------------------------
# T12 — per-agent override. DOC §"You can override permissions per agent.
# Agent permissions are merged with the global config, and agent rules take
# precedence." Worked example: global shell { "*": "ask", "git *": "allow",
# "git commit *": "deny", "git push *": "deny", "grep *": "allow" }, agent
# "build" shell { "*": "ask", "git *": "allow", "git commit *": "ask",
# "git push *": "deny", "grep *": "allow" }.
# --------------------------------------------------------------------------
global_shell = {"*": "ask", "git *": "allow", "git commit *": "deny",
                "git push *": "deny", "grep *": "allow"}
agent_build_shell = {"*": "ask", "git *": "allow", "git commit *": "ask",
                     "git push *": "deny", "grep *": "allow"}
check("T12a agent ask beats global deny for 'git commit -m x'",
      ev({"shell": global_shell}, "shell", "git commit -m x",
         agent_permission={"shell": agent_build_shell}).decision == "prompt")
check("T12b without agent the global deny stands",
      ev({"shell": global_shell}, "shell", "git commit -m x").decision == "forbidden")
check("T12c agent and global agree on 'git push origin' -> deny",
      ev({"shell": global_shell}, "shell", "git push origin",
         agent_permission={"shell": agent_build_shell}).decision == "forbidden")

# --------------------------------------------------------------------------
# T13 — markdown agent frontmatter style. DOC:
#   permission: { edit: deny, shell: ask, webfetch: deny }
# --------------------------------------------------------------------------
md_agent = {"edit": "deny", "shell": "ask", "webfetch": "deny"}
check("T13 markdown frontmatter agent permission",
      ev({}, "shell", "ls", agent_permission=md_agent).decision == "prompt"
      and ev({}, "edit", "x", agent_permission=md_agent).decision == "forbidden"
      and ev({}, "webfetch", "https://x.example/",
             agent_permission=md_agent).decision == "forbidden",
      "DOC §'You can also configure agent permissions in Markdown'")

# --------------------------------------------------------------------------
# T14 — no-match -> unknown with layer attribution (framework rule INV-005;
# vendor runtime default documented as attribution only, never measured).
# --------------------------------------------------------------------------
r = ev({"shell": {"git *": "allow"}}, "shell", "curl https://example.com")
check("T14a no matching pattern -> unknown, never allow",
      r.decision == "unknown" and r.matched == [])
check("T14b attribution names the runtime default without claiming it",
      "runtime default" in r.notes[0] and "never allow" in r.notes[0],
      "got %r" % (r.notes,))
r = ev({}, "shell", "ls")
check("T14c tool key absent entirely -> unknown",
      r.decision == "unknown")

# --------------------------------------------------------------------------
# T15 — precedence probes in both orders (the framework's sharpest
# inter-harness contrast). Translated prec_a/prec_b preserving order.
# --------------------------------------------------------------------------
def prec_cfg(text):
    pairs = E.translate_prefix_rules(text)
    return {"shell": dict(pairs)}

prec_a = 'prefix_rule(pattern=["git"], decision="prompt")\nprefix_rule(pattern=["git", "status"], decision="allow")'
prec_b = 'prefix_rule(pattern=["git", "status"], decision="allow")\nprefix_rule(pattern=["git"], decision="prompt")'
check("T15a prec_a order (prompt first): 'git status' -> allow (last wins)",
      ev(prec_cfg(prec_a), "shell", "git status").decision == "allow")
check("T15b prec_b order (allow first): 'git status' -> prompt (last wins)",
      ev(prec_cfg(prec_b), "shell", "git status").decision == "prompt")
prec_d = 'prefix_rule(pattern=["git", "status"], decision="forbidden")\nprefix_rule(pattern=["git", "status"], decision="allow")'
check("T15c identical patterns forbidden-then-allow -> allow",
      ev(prec_cfg(prec_d), "shell", "git status").decision == "allow")
check("T15d translation rule: 'prefix_rule([t1..tn], d)' -> 't1 .. tn*' verb",
      E.translate_prefix_rules(
          'prefix_rule(pattern=["rm", "-rf"], decision="forbidden")')
      == [("rm -rf*", "deny")])

# --------------------------------------------------------------------------
# T16 — normalization assumption: single-space join of argv.
# --------------------------------------------------------------------------
check("T16 normalize_command is the documented single-space join",
      E.normalize_command(["git", "status"]) == "git status"
      and E.normalize_command(["bash", "-lc", "rm -rf /"]) == "bash -lc rm -rf /",
      "policy/README.md §Explicit normalization assumption")

# --------------------------------------------------------------------------
# T17 — policy fixtures on disk: swapped is the exact reverse of baseline.
# --------------------------------------------------------------------------
pol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy")
base = json.load(open(os.path.join(pol, "opencode.json")))
swap = json.load(open(os.path.join(pol, "policy.order-swapped.json")))
bk = list(base["permission"]["shell"].items())
sk = list(swap["permission"]["shell"].items())
check("T17a order-swapped fixture is the exact reverse of baseline",
      sk == list(reversed(bk)), "got %r" % (sk,))
check("T17b baseline preserves default.rules order + translation",
      bk == [("git status*", "allow"), ("deployctl release*", "ask"),
             ("rm -rf*", "deny"), ("rm -fr*", "deny"),
             ("rm --recursive --force*", "deny")])
pbase = json.load(open(os.path.join(pol, "protected-records.json")))
pswap = json.load(open(os.path.join(pol, "protected-records.order-swapped.json")))
check("T17c protected pair: swapped is the exact reverse",
      list(pswap["permission"]["shell"].items())
      == list(reversed(list(pbase["permission"]["shell"].items()))))

# --------------------------------------------------------------------------
print()
if FAILURES:
    print("FAILURES: %d -> %s" % (len(FAILURES), FAILURES))
    sys.exit(1)
print("ALL TESTS PASSED")
