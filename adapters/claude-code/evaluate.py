#!/usr/bin/env python3
"""
Claude Code T2 config-evaluation engine.

Implements the DOCUMENTED permission-matching semantics of Claude Code
(@anthropic-ai/claude-code@2.1.307, docs retrieved 2026-10-22) against a
settings.json `permissions` object. This is a labelled reimplementation of
the vendor's documented matching semantics — it NEVER interrogates a native
oracle (none exists). Every result it produces is evidence class
"T2-evaluation (never interrogated)".

Documented semantics modelled (https://code.claude.com/docs/en/permissions):
  1. Rules are evaluated in order: deny, then ask, then allow. The first
     match in that order determines the outcome; rule specificity does not
     change the order. A broad deny blocks even when a narrower allow also
     matches; a matching ask prompts even when a more specific allow also
     matches.
  2. A rule is a bare tool name (matches every use of that tool) or
     Tool(specifier). Bare `Bash` and `Bash(*)` both match all Bash commands.
     As a deny rule, a bare tool name removes the tool from the model's
     context (recorded as a layer-vocabulary ambiguity, not modelled).
  3. Bash rules match the command text as written, with `*` standing in for
     any text (including spaces). No `*` -> exact command match. See the
     wildcard table in the docs (unit-tested row by row in test_engine.py).
  4. A trailing ` *` that is the rule's ONLY wildcard also matches the bare
     command: `Bash(ls *)` matches `ls` (and `ls -la`, not `lsof`).
     `Bash(* --help *)` has two wildcards, so `npm --help` does NOT match.
  5. The `:*` suffix is equivalent to a trailing ` *`, recognised only at the
     end of a pattern: `Bash(ls:*)` == `Bash(ls *)`.
  6. Compound commands: deny and ask rules apply when ANY subcommand matches
     them (including inside subshells/command substitutions — subcommand
     extraction here is top-level splitting on &&, ||, ; and |, quotes
     respected; deeper nesting is a documented ceiling, not modelled).
     A compound command runs without a prompt only when each part qualifies
     on its own (allow rule or built-in read-only set).
  7. Wrappers stripped before matching (fixed built-in list, not
     configurable): timeout, time, nice, nohup, stdbuf, the shell builtins
     command and builtin, zsh's noglob; bare xargs with no flags.
     `command -v` (query form) is NOT stripped. `timeout 30` strips the
     wrapper AND its duration argument (docs example: `Bash(npm test *)`
     matches `timeout 30 npm test`).
  8. A leading assignment of certain known-safe env vars is stripped for
     allow matching (only NODE_ENV is named in the docs). Deny/ask rules
     match past ANY leading assignment (`Bash(rm *)` in deny still matches
     `FOO=bar rm -rf tmp/`).
  9. No rule match -> the command would prompt the user (Manual/default
     mode). In the shared finding vocabulary this serializes as `unknown`
     with layer attribution ("no rules-layer decision"), NEVER as allow.
 10. Built-in read-only command set runs without a permission prompt in
     every mode (docs): ls, cat, echo, pwd, head, tail, grep, find, wc,
     which, diff, stat, du, cd, and read-only forms of git. Exceptions
     (unquoted globs for write-capable flags, find with -exec/-delete/-fprint
     etc., >10k chars) are modelled conservatively; anything ambiguous is
     NOT treated as read-only. A read-only allowance is recorded as
     `allow` with layer note "builtin-read-only (not a rules-layer
     decision)"; in auto mode these may still await classifier review.

Deliberately NOT modelled (T2 ceilings, recorded not simulated):
  - PreToolUse/PreCompact hooks (arbitrary user code)
  - the stochastic auto-mode classifier (`claude auto-mode config` only
    prints config; it is not a per-command oracle)
  - permission modes other than default/manual (dontAsk, bypassPermissions,
    plan, auto) and the six mode overlays
  - sandbox settings sub-keys (unconfirmed in official docs)
  - redirect-target file-rule checks, tee targets, WebFetch/Read/Edit rules
  - exec-wrapper/find-action prompt exceptions beyond the read-only model
  - `defaultMode`, managed/org settings layering
"""

import json
import re
import sys

DOC_PERMISSIONS_URL = "https://code.claude.com/docs/en/permissions"

# Fixed wrapper set, per docs ("Wrappers" section). `command -v` (query form)
# and zsh's `nocorrect` are explicitly NOT stripped.
STRIP_WRAPPERS = {"timeout", "time", "nice", "nohup", "stdbuf",
                  "command", "builtin", "noglob"}
# Only named known-safe env var in the docs ("Wrappers" section).
KNOWN_SAFE_ENV_ASSIGN = {"NODE_ENV"}

# Built-in read-only Bash commands (docs, "Read-only commands" section).
BUILTIN_READONLY = {"ls", "cat", "echo", "pwd", "head", "tail", "grep",
                    "find", "wc", "which", "diff", "stat", "du", "cd"}
# Conservative subset of "read-only forms of git" (docs do not enumerate
# the full version-defined set; only unambiguous read-only subcommands).
GIT_READONLY_SUBCOMMANDS = {"status", "log", "diff", "show", "branch",
                            "rev-parse", "ls-files", "blame", "describe",
                            "tag", "remote"}
# find actions that make find write/exec-capable -> prompt (docs).
FIND_WRITE_ACTIONS = {"-exec", "-delete", "-rm", "-fprint", "-files0-from",
                      "-execdir", "-ok", "-okdir", "-fls", "-fprint0"}


def split_compound(command):
    """Split a command string into top-level subcommands on &&, ||, ; and |.

    Quote-aware (single/double quotes). Deeper nesting (subshells, command
    substitution, for-loop bodies) is a documented ceiling: we do not recurse.
    """
    parts, cur = [], []
    i, n = 0, len(command)
    quote = None
    while i < n:
        ch = command[i]
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            cur.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            cur.append(ch)
            cur.append(command[i + 1])
            i += 2
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            parts.append("".join(cur).strip())
            cur = []
            i += 2
            continue
        if ch in (";", "|"):
            parts.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def _is_assignment(tok):
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok) is not None


def _nested_candidates(text, _depth=0):
    """Extract nested command texts from $(...), and `...` substitutions.

    Docs ("Compound commands"): deny and ask rules apply when any subcommand
    matches them, "including a command nested inside a subshell, a command
    substitution, or a control-flow body such as a for loop". We extract
    $(...) and backtick substitutions (quote-aware: single quotes suppress
    substitution in shell). Bare ( ... ) subshells and for-loop bodies are a
    documented ceiling, not modelled.
    """
    if _depth > 4:
        return []
    out = []
    i, n = 0, len(text)
    squote = False  # single quotes suppress substitution entirely
    while i < n:
        ch = text[i]
        if squote:
            if ch == "'":
                squote = False
            i += 1
            continue
        if ch == "'":
            squote = True
            i += 1
            continue
        if ch == "\\":
            i += 2
            continue
        if text.startswith("$(", i):
            depth = 1
            j = i + 2
            q2 = None
            while j < n and depth:
                c2 = text[j]
                if q2:
                    if c2 == q2:
                        q2 = None
                elif c2 in ("'", '"'):
                    q2 = c2
                elif c2 == "\\":
                    j += 1
                elif c2 == "(":
                    depth += 1
                elif c2 == ")":
                    depth -= 1
                j += 1
            inner = text[i + 2:j - 1]
            out.append(inner)
            out.extend(_nested_candidates(inner, _depth + 1))
            i = j
            continue
        if ch == "`":
            j = text.find("`", i + 1)
            if j == -1:
                break
            inner = text[i + 1:j]
            out.append(inner)
            out.extend(_nested_candidates(inner, _depth + 1))
            i = j + 1
            continue
        i += 1
    return out


def _deny_ask_candidates(subcommand):
    """Top-level subcommand plus nested substitution candidates.

    Deny/ask rules are matched against every candidate; allow rules are
    matched only against the top-level subcommand (docs specify nested
    behaviour for deny/ask only).
    """
    return [subcommand] + _nested_candidates(subcommand)


def strip_wrappers(subcommand, for_allow):
    """Strip the documented wrapper layer before matching.

    for_allow=False (deny/ask evaluation): strip any leading VAR=value
    assignments. for_allow=True: strip only known-safe assignments
    (NODE_ENV per docs).
    """
    toks = subcommand.split()
    # strip wrapper tokens
    while toks and toks[0] in STRIP_WRAPPERS:
        w = toks.pop(0)
        if w == "command" and toks and toks[0] == "-v":
            # query form `command -v` is NOT stripped: put the wrapper back
            toks.insert(0, "command")
            break
        if w == "timeout" and toks:
            toks.pop(0)  # duration argument, per docs example
    # bare xargs with no flags is stripped; `xargs -n1 grep pattern` (or any
    # flag-bearing xargs) is matched as an xargs command, so rules written
    # for the inner command do not cover it. Heuristic: strip only when the
    # token immediately after xargs does not start with "-".
    if toks and toks[0] == "xargs":
        if len(toks) > 1 and not toks[1].startswith("-"):
            toks.pop(0)
    # leading env assignments
    while toks and _is_assignment(toks[0]):
        name = toks[0].split("=", 1)[0]
        if for_allow and name not in KNOWN_SAFE_ENV_ASSIGN:
            break
        toks.pop(0)
    return " ".join(toks)


def _glob_regex(spec):
    out = []
    for ch in spec:
        out.append(".*" if ch == "*" else re.escape(ch))
    return "".join(out)


def bash_rule_matches(rule_spec, command):
    """Does a Bash rule specifier match the command text? (docs wildcard table)

    rule_spec is the inside of Bash(...). Implements:
      - `:*` suffix == trailing ` *` (only at end of pattern)
      - `*` = any text including spaces; no `*` = exact match
      - single trailing ` *` also matches the bare command
    """
    spec = rule_spec
    if spec.endswith(":*"):
        spec = spec[:-2] + " *"
    if spec == "*" or spec == "":
        return True  # Bash(*) == bare Bash: matches every Bash command
    if re.fullmatch(_glob_regex(spec), command):
        return True
    if spec.endswith(" *") and spec.count("*") == 1 and command == spec[:-2]:
        return True  # trailing-`*` bare-command concession
    return False


def _has_unquoted_glob(text):
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "*" and not (i > 0 and text[i - 1] == "\\"):
            return True
    return False


def is_builtin_readonly(subcommand):
    """Conservative model of the documented built-in read-only set."""
    if len(subcommand) > 10000:
        return False  # docs: >10k chars always prompts
    toks = subcommand.split()
    if not toks:
        return False
    prog = toks[0]
    rest = toks[1:]
    if prog == "git":
        if not rest or rest[0].startswith("-"):
            return False  # conservative: no flag-leading or bare git
        if rest[0] not in GIT_READONLY_SUBCOMMANDS:
            return False
    elif prog not in BUILTIN_READONLY:
        return False
    if _has_unquoted_glob(subcommand):
        # unquoted globs prompt for commands with write-capable flags
        # (find, sort, sed, git). Conservative: any unquoted glob -> not
        # treated as read-only.
        return False
    if prog == "find" and any(a in FIND_WRITE_ACTIONS for a in rest):
        return False
    return True


def parse_rule(rule):
    """Parse 'Tool' or 'Tool(specifier)' -> (tool, specifier|None)."""
    m = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*)(?:\((.*)\))?", rule,
                     re.DOTALL)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _matches_in_list(rule_list, subcommand, for_allow, nested=True):
    stripped = strip_wrappers(subcommand, for_allow=for_allow)
    candidates = _deny_ask_candidates(stripped) if nested else [stripped]
    hits = {}
    for cand in candidates:
        for rule in rule_list:
            tool, spec = parse_rule(rule)
            if tool != "Bash":
                continue  # this engine evaluates Bash tool calls only
            if spec is None or bash_rule_matches(spec, cand):
                hits.setdefault(rule, []).append(cand)
    return hits


def evaluate(command_text, permissions):
    """Evaluate one Bash command text against a permissions object.

    Returns a dict with the shared-vocabulary decision plus evidence.
    """
    subcommands = split_compound(command_text)
    allow_rules = permissions.get("allow", [])
    ask_rules = permissions.get("ask", [])
    deny_rules = permissions.get("deny", [])

    deny_hits = {}
    for sub in subcommands:
        hits = _matches_in_list(deny_rules, sub, for_allow=False)
        if hits:
            deny_hits[sub] = hits
    if deny_hits:
        return {
            "decision": "forbidden",
            "matched_rules": deny_hits,
            "layer": "rules",
            "note": "deny rule matched (deny evaluated before ask/allow; "
                    "first match wins; specificity irrelevant)",
        }

    ask_hits = {}
    for sub in subcommands:
        hits = _matches_in_list(ask_rules, sub, for_allow=False)
        if hits:
            ask_hits[sub] = hits
    if ask_hits:
        return {
            "decision": "prompt",
            "matched_rules": ask_hits,
            "layer": "rules",
            "note": "ask rule matched (ask evaluated before allow; "
                    "first match wins)",
        }

    uncovered = []
    for sub in subcommands:
        allow_hits = _matches_in_list(allow_rules, sub, for_allow=True)
        if allow_hits:
            continue
        if is_builtin_readonly(sub):
            continue
        uncovered.append(sub)
    if not uncovered:
        ro = [s for s in subcommands
              if not _matches_in_list(allow_rules, s, for_allow=True)]
        return {
            "decision": "allow",
            "matched_rules": {},
            "layer": "rules",
            "note": ("every subcommand covered by an allow rule"
                     + ("; subcommand(s) %s allowed via the documented "
                        "built-in read-only set (not a rules-layer decision; "
                        "may still await classifier review in auto mode)"
                        % ro if ro else "")),
        }

    return {
        "decision": "unknown",
        "matched_rules": {},
        "layer": "rules",
        "note": ("no rules-layer decision for subcommand(s) %s; in "
                 "Manual/default mode the harness would prompt the user. "
                 "Recorded as unknown with layer attribution, never as "
                 "allow." % uncovered),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--command", required=True)
    args = ap.parse_args()
    perms = json.load(open(args.policy))["permissions"]
    print(json.dumps(evaluate(args.command, perms), indent=2))


if __name__ == "__main__":
    main()
