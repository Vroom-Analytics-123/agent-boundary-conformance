#!/usr/bin/env python3
"""FinePrint free gate: a wrapper-level guard for local + CI use.

Adapted from the paid-product prototype's decision logic
(program repo, paid-product/gate.py) with one hardening the prototype
lacked: path decisions run on the REALPATH (symlinks resolved), so a
symlink inside an allowed directory that points outside is denied.
The audit log is the prototype's hash-chained JSONL design, unchanged
in shape.

What this is: a tripwire + a wall + an audit trail for the common
paths. The default policy is a PROTECTIVE DENYLIST (antivirus for
agents): out of the box it blocks known-dangerous patterns from
Catalogue v1 + our discovered issues — credential reads (SSH keys,
.env, tokens, the records file), destructive deletes, exfiltration
of protected files, unapproved deploys, and the bypasses we measured
(read-tool credential escape, unlink-around-rm-filter). Normal work
anywhere is allowed by default. Folder confinement (an allowlist of
folders) is OPT-IN (`--confine` / policy "mode": "confine").

`gate run` pre-flights a command (the tripwire: refuses it when an
argument names a protected path or host, or the command itself
matches a denied pattern), then runs it INSIDE the wall
(tools/fineprint_wall.py — the agent runs in a sandbox built from the
OS `unshare` primitive; in denylist mode the protected targets are
hidden, in confine mode everything outside the allowed scope is
hidden). `gate check` answers one allow/deny question.
`gate definitions` reports the denylist version in force.
`gate log` renders the audit log as readable notifications.
`gate verify-log` checks the audit log's hash chain.

Every blocked attempt is a structured event: what the agent tried,
which rule stopped it, and the fact that the same action will always
be denied — deterministic (policy, not model judgment). The audit
log carries the rule id and a `deterministic: true` marker on every
denial, so the app can render them as notifications.

What this is NOT (read docs/FREE_GATE.md before trusting it):
  - The wall enforces SCOPE (paths and hosts), not intent. An agent
    that misuses a file INSIDE the allowed scope is out of scope for
    the wall; that is Check's job (Catalogue v1).
  - The wall does not isolate the process table, and its proxy
    controls egress only for tools that honor proxy env vars (see
    FREE_GATE.md for the bypass limits, stated plainly).
  - `gate run --no-wall` runs tripwire-only (not enforced) — an
    explicit opt-out for debugging, never the default. The default
    refuses to run when the sandbox tool is missing, rather than
    silently falling back to the tripwire.
  - A bare word that resolves to a normal file is allowed in denylist
    mode: the gate checks what a command is asked to touch against
    the denylist, not what it might do. `gate run` takes argv
    directly (no shell), so shell redirections cannot even be
    expressed through it.

Deny-by-default for what it scans: anything the denylist names is
denied, and in confine mode anything outside the allowed scope is
denied. Unknown action kinds are denied. A decision is never
silently allow.

Stdlib only. Usage:
  python3 tools/fineprint_gate.py check --file PATH --policy FILE
  python3 tools/fineprint_gate.py check --host HOST --policy FILE
  python3 tools/fineprint_gate.py run --policy FILE [--log FILE] [--no-wall] [--confine] -- CMD...
  python3 tools/fineprint_gate.py definitions
  python3 tools/fineprint_gate.py log --log FILE
  python3 tools/fineprint_gate.py verify-log --log FILE
  (the `fineprint` CLI wraps these; see `fineprint gate --help`)
"""

import fnmatch
import hashlib
import json
import os
import shlex
import subprocess
import sys
import threading
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fineprint_definitions as D  # noqa: E402

EXIT_ALLOW = 0
EXIT_DENY = 2
EXIT_ERROR = 3


@dataclass(frozen=True)
class Action:
    kind: str  # "file_read" | "file_write" | "network"
    target: str  # file path or hostname/URL


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    rule: str = ""  # the denylist/confine rule that decided, if any


def _realpath(path):
    """Resolve symlinks + .. segments. Non-existent tails are kept."""
    return os.path.realpath(path)


class Policy:
    """Two modes. "deny" (the default) is the protective denylist:
    anything the definitions name is denied, everything else is
    allowed. "confine" is the folder allowlist: anything outside the
    allowed paths/hosts is denied, on top of the denylist. Paths are
    checked on their realpath; hosts are matched exactly
    (case-insensitive)."""

    def __init__(self, allowed_paths=(), allowed_hosts=(), mode="deny",
                 denied_paths=(), denied_hosts=(), allowed_commands=()):
        self.mode = mode if mode in ("deny", "confine") else "deny"
        self.allowed_paths = tuple(
            _realpath(p) for p in allowed_paths)
        self.allowed_hosts = tuple(h.lower() for h in allowed_hosts)
        self.denied_paths = tuple(denied_paths)
        self.denied_hosts = tuple(h.lower() for h in denied_hosts)
        self.allowed_commands = tuple(allowed_commands)

    @classmethod
    def from_file(cls, path):
        doc = json.loads(Path(path).read_text())
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: policy must be a JSON object")
        return cls.from_dict(doc)

    @classmethod
    def from_dict(cls, doc):
        return cls(doc.get("allowed_paths", ()),
                   doc.get("allowed_hosts", ()),
                   mode=doc.get("mode", "deny"),
                   denied_paths=doc.get("denied_paths", ()),
                   denied_hosts=doc.get("denied_hosts", ()),
                   allowed_commands=doc.get("allowed_commands", ()))

    def _denied_path_rule(self, real, rules):
        """The rule id for a resolved path, or None."""
        rule = D.path_rule(real, rules)
        if rule:
            return rule
        import fnmatch
        for pattern in self.denied_paths:
            if fnmatch.fnmatch(real, pattern):
                return "DENY-PATH"
        return None

    def decide(self, action, rules=None):
        rules = rules if rules is not None else D.builtin_rules()
        if action.kind in ("file_read", "file_write"):
            target = action.target
            real = _realpath(target)
            rule = self._denied_path_rule(real, rules)
            if rule:
                return Decision(False, f"{action.kind} of a protected "
                                       f"path: {target!r} resolves to "
                                       f"{real!r}", rule=rule)
            if self.mode == "confine":
                if ".." in Path(target).parts:
                    return Decision(False, "path traversal rejected: "
                                           f"{target!r} contains '..'",
                                    rule="CONFINE-PATH")
                for prefix in self.allowed_paths:
                    if real == prefix or real.startswith(
                            prefix.rstrip(os.sep) + os.sep):
                        return Decision(
                            True, f"{action.kind} under allowed path {prefix}")
                return Decision(False, f"{action.kind} outside allowed "
                                       f"paths: {target!r} resolves to "
                                       f"{real!r}", rule="CONFINE-PATH")
            return Decision(True, f"{action.kind} of a normal path: "
                                  f"{target!r}")
        if action.kind == "network":
            host = _host_of(action.target)
            rule = D.host_rule(host, rules)
            if rule:
                return Decision(False, f"host {host} denied by "
                                       f"definitions", rule=rule)
            if host in self.denied_hosts:
                return Decision(False, f"host {host} denied by policy",
                                rule="DENY-HOST")
            if self.mode == "confine":
                if host in self.allowed_hosts:
                    return Decision(True, f"host {host} allowlisted")
                return Decision(False, f"host {host} not allowlisted",
                                rule="CONFINE-HOST")
            return Decision(True, f"host {host} not denied")
        return Decision(False, f"unknown action kind {action.kind!r}")


def _host_of(target):
    """A bare hostname, or the host of an http(s) URL."""
    if "://" in target:
        return (urllib.parse.urlparse(target).hostname or "").lower()
    return target.lower().split("/")[0].split(":")[0]


class AuditLog:
    """Append-only JSONL log. Each entry hashes the previous entry's hash,
    so any edit to an earlier entry breaks verification of everything
    after. Same shape as the paid-product prototype's log.

    Entries carry an optional `event` (e.g. WALL_START) and optional
    extra top-level fields (e.g. the wall's sandbox_tool) — the entry
    shape for gate decisions ({action, allowed, reason, note,
    prev_hash, hash}) is unchanged. Appends are serialized with a lock
    so the wall's proxy threads cannot interleave and break the chain.
    """

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self.prev_hash = "0" * 64
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path) as f:
                for line in f:
                    if line.strip():
                        self.prev_hash = json.loads(line)["hash"]

    def append(self, action, decision, note="", event=None, extra=None):
        # The whole read-hash-write is one critical section: two
        # concurrent appends must not read the same prev_hash.
        with self._lock:
            entry = {
                "action": {"kind": action.kind, "target": action.target},
                "allowed": decision.allowed,
                "reason": decision.reason,
                "note": note,
                "prev_hash": self.prev_hash,
            }
            if event is not None:
                entry["event"] = event
            if extra:
                entry.update(extra)
            # Every denial is a structured, deterministic event: the
            # rule that stopped it and the fact that the same action
            # will always be denied (policy, not model judgment).
            if not decision.allowed:
                entry["deterministic"] = True
                if decision.rule:
                    entry["rule"] = decision.rule
            blob = json.dumps(entry, sort_keys=True).encode()
            entry["hash"] = hashlib.sha256(blob).hexdigest()
            with open(self.path, "a") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
            self.prev_hash = entry["hash"]
            return entry

    @staticmethod
    def verify(path):
        prev = "0" * 64
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                h = entry.pop("hash")
                if entry["prev_hash"] != prev:
                    return False
                blob = json.dumps(entry, sort_keys=True).encode()
                if hashlib.sha256(blob).hexdigest() != h:
                    return False
                prev = h
        return True


class Gate:
    def __init__(self, policy, log=None, definitions=None):
        self.policy = policy
        self.log = log
        # (version, rules, source); loads (and verifies) the pack when
        # not given. Raises fineprint_definitions.DefinitionsError
        # when a pack file is present but does not verify.
        self.definitions = (definitions if definitions is not None
                            else D.load_definitions())
        self.rules = self.definitions[1]

    def evaluate(self, action, note=""):
        decision = self.policy.decide(action, self.rules)
        if self.log is not None:
            self.log.append(action, decision, note=note)
        return decision

    def check_command(self, argv, note=""):
        """The command itself, not just its arguments: denied command
        patterns (destructive delete, unlink, deploy), exfiltration
        of a protected file, and the allowed_commands override.
        Returns a Decision (allow when nothing matches)."""
        decision = self._check_command(argv)
        if self.log is not None and not decision.allowed:
            self.log.append(Action("exec", " ".join(argv)), decision,
                            note=note or "pre-flight: " + " ".join(argv))
        return decision

    def _check_command(self, argv):
        if not argv:
            return Decision(True, "no command")
        base = os.path.basename(argv[0])
        # An explicitly allowed command overrides the denylist.
        for pattern in self.policy.allowed_commands:
            if fnmatch.fnmatch(base, pattern) or \
                    fnmatch.fnmatch(argv[0], pattern):
                return Decision(True, f"command {base!r} explicitly "
                                      f"allowed by policy")
        # Unwrap wrappers (F1): every effective command is checked
        # against the denylist, not just the outer argv[0] — `bash -lc
        # "rm -rf …"` and `env rm -rf …` used to delete straight
        # through the wall.
        for inner in unwrap_argv(argv):
            decision = self._check_single_command(inner, argv)
            if not decision.allowed:
                return decision
        return Decision(True, "command not denied")

    def _check_single_command(self, inner, outer):
        """One effective argv against the denylist."""
        if not inner:
            return Decision(True, "no command")
        base = os.path.basename(inner[0])
        # An explicitly allowed inner command overrides the denylist.
        for pattern in self.policy.allowed_commands:
            if fnmatch.fnmatch(base, pattern) or \
                    fnmatch.fnmatch(inner[0], pattern):
                return Decision(True, f"command {base!r} explicitly "
                                      f"allowed by policy")
        wrapped = (" (unwrapped from " + " ".join(outer) + ")"
                   if inner != outer else "")
        # Exfiltration: a copy/send command naming a protected file.
        # The rule id is synthetic (F2): declared in
        # fineprint_definitions.SYNTHETIC_RULES, not a pack rule.
        if base in ("cp", "scp", "rsync", "curl", "wget"):
            for tok in inner[1:]:
                if tok.startswith("-"):
                    continue
                real = _realpath(tok)
                if self.policy._denied_path_rule(real, self.rules):
                    return Decision(False, f"exfiltration of a protected "
                                           f"file: {tok!r} resolves to "
                                           f"{real!r}{wrapped}",
                                    rule=D.DENY_EXFIL_ID)
        rule = D.command_rule(inner, self.rules)
        if rule:
            desc = next((r.get("description", "") for r in self.rules
                         if r["id"] == rule), "")
            return Decision(False, f"command denied by definitions "
                                   f"({desc}): {' '.join(inner)}{wrapped}",
                            rule=rule)
        return Decision(True, "command not denied")


# ---------------------------------------------------------------------------
# Wrapper unwrapping (F1)
# ---------------------------------------------------------------------------
# A tripwire that only looks at argv[0] is trivially routed around:
# `bash -lc "rm -rf …"` and `env rm -rf …` deleted the target through
# the wall, and `sudo rm -rf …` survived only because sudo itself broke
# inside the user namespace. So the tripwire unwraps the wrappers an
# agent reaches for — sudo/doas, env, su -c, nice/time/xargs, and shells
# with -c — and re-checks the inner command against the denylist.
# Every effective command is checked; a shell -c string is split on
# operators (;, &&, ||, |) and commands inside $(...), `...`, <(...) and
# >(...) are checked too, because they still execute. What this does
# NOT do: parse arbitrary shell. A -c string shlex cannot parse is one
# bash itself rejects (unbalanced quote), so nothing executes; the
# original argv is checked instead. A command hidden in a script file
# (`bash deploy.sh`) is out of scope for the tripwire — the wall hides
# protected paths, and deploy-via-script is recorded as not-covered
# (see docs/FREE_GATE.md).

_SHELL_NAMES = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
_SUDO_LIKE = {"sudo", "doas"}
_SU_LIKE = {"su", "runuser"}
_NICE_LIKE = {"nice", "time"}
# Short-option characters that take a value (the rest of the bundle,
# else the next token, is the value).
_SUDO_SHORT_VALUE = set("ughpCDrtU")
_SUDO_LONG_VALUE = {"--user", "--group", "--host", "--prompt", "--chdir",
                    "--role", "--type"}
_ENV_SHORT_VALUE = set("uCS")
_ENV_LONG_VALUE = {"--unset", "--chdir", "--split-string"}
_NICE_SHORT_VALUE = set("n")
_NICE_LONG_VALUE = {"--adjustment"}
_TIME_SHORT_VALUE = set()
_TIME_LONG_VALUE = {"--output", "--format"}
_XARGS_SHORT_VALUE = set("InPLdEas")
_XARGS_LONG_VALUE = {"--replace", "--max-args", "--max-procs",
                     "--max-lines", "--delimiter", "--eof", "--arg-file",
                     "--max-chars"}


def _skip_options(args, i, short_value, long_value):
    """Index of the first non-option token at/after i.

    Skips short bundles ("-nu" — a value-opt char consumes the rest
    of the bundle or the next token), long options ("--opt" /
    "--opt=v", value-taking ones consume the next token when no "="
    is present), and "--" (everything after it is the command)."""
    n = len(args)
    while i < n:
        tok = args[i]
        if tok == "--":
            return i + 1
        if tok.startswith("--"):
            name, eq, _ = tok.partition("=")
            if name in long_value and not eq:
                i += 2
                continue
            i += 1
            continue
        if tok.startswith("-") and len(tok) > 1:
            chars = tok[1:]
            j = 0
            take_next = False
            while j < len(chars):
                if chars[j] in short_value:
                    if j + 1 == len(chars):
                        take_next = True
                    break
                j += 1
            i += 2 if take_next else 1
            continue
        return i
    return i


def _shell_command_string(args):
    """The command string of a `sh -c "…"` invocation, or None.

    Handles "-c", "-lc", "-ic" (the 'c' in a short bundle takes the
    rest of the bundle, else the next token, as its argument). A
    bare "-" is a skippable option (login shell). A non-option token
    first means a script file, not -c."""
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--":
            return None
        if tok == "-":
            i += 1
            continue
        if tok.startswith("--"):
            i += 1
            continue
        if tok.startswith("-") and len(tok) > 1:
            chars = tok[1:]
            if "c" in chars:
                pos = chars.index("c")
                if pos + 1 < len(chars):
                    return chars[pos + 1:]
                if i + 1 < len(args):
                    return args[i + 1]
                return None
            i += 1
            continue
        return None
    return None


def _subshell_strings(s):
    """Command strings inside $(...), `...`, <(...) and >(...) in s.

    Quote-naive (a quoted literal is treated as executed): it may
    overblock a literal, never underblock an executed command."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s.startswith("$(", i) or s.startswith("<(", i) or \
                s.startswith(">(", i):
            depth = 1
            j = i + 2
            while j < n and depth:
                if s[j] == "(":
                    depth += 1
                elif s[j] == ")":
                    depth -= 1
                j += 1
            out.append(s[i + 2:j - 1])
            i = j
        elif s[i] == "`":
            j = s.find("`", i + 1)
            if j == -1:
                break
            out.append(s[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


def _shell_command_argvs(cmd_string):
    """A `sh -c` string as a list of per-command argvs.

    Splits on shell operators (;, &&, ||, |) and checks commands
    inside $(...), `...`, <(...) and >(...) too. Returns None when
    the string cannot be parsed — bash itself rejects such strings
    (unbalanced quote), so nothing executes; the caller then checks
    the original argv."""
    lexer = shlex.shlex(cmd_string, posix=True, punctuation_chars=";|&")
    lexer.commenters = ""  # a '#' is literal here, never a comment
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    segments, cur = [], []
    for tok in tokens:
        if tok in (";", "|", "&", "&&", "||"):
            if cur:
                segments.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        segments.append(cur)
    for inner in _subshell_strings(cmd_string):
        sub = _shell_command_argvs(inner)
        if sub is None:
            return None
        segments.extend(sub)
    return segments


def unwrap_argv(argv):
    """The effective command(s) behind wrappers, as a list of argvs.

    `sudo rm -rf x` -> [["rm", "-rf", "x"]]; `bash -lc "rm -rf x"`
    -> [["rm", "-rf", "x"]]; a plain command unwraps to itself. A
    shell -c string with several commands yields one argv per
    command. Unwrapping is recursive (`sudo env bash -c …`)."""
    if not argv:
        return []
    base = os.path.basename(argv[0])
    if base in _SHELL_NAMES:
        cmd = _shell_command_string(argv[1:])
        if cmd is None:
            return [list(argv)]
        segments = _shell_command_argvs(cmd)
        if segments is None:
            return [list(argv)]
        out = []
        for seg in segments:
            out.extend(unwrap_argv(seg))
        return out or [list(argv)]
    if base in _SUDO_LIKE:
        i = _skip_options(argv, 1, _SUDO_SHORT_VALUE, _SUDO_LONG_VALUE)
        if i >= len(argv):
            return [list(argv)]
        return unwrap_argv(argv[i:])
    if base == "env":
        i = _skip_options(argv, 1, _ENV_SHORT_VALUE, _ENV_LONG_VALUE)
        # VAR=value assignments are not the command.
        while i < len(argv) and "=" in argv[i] and \
                not argv[i].startswith("-"):
            i += 1
        if i >= len(argv):
            return [list(argv)]
        return unwrap_argv(argv[i:])
    if base in _SU_LIKE:
        args = argv[1:]
        if args and not args[0].startswith("-"):
            args = args[1:]  # the user
        cmd = _shell_command_string(args)
        if cmd is None:
            return [list(argv)]
        segments = _shell_command_argvs(cmd)
        if segments is None:
            return [list(argv)]
        out = []
        for seg in segments:
            out.extend(unwrap_argv(seg))
        return out or [list(argv)]
    if base in _NICE_LIKE:
        if base == "nice":
            short, long = _NICE_SHORT_VALUE, _NICE_LONG_VALUE
        else:
            short, long = _TIME_SHORT_VALUE, _TIME_LONG_VALUE
        i = _skip_options(argv, 1, short, long)
        if i >= len(argv):
            return [list(argv)]
        return unwrap_argv(argv[i:])
    if base == "xargs":
        i = _skip_options(argv, 1, _XARGS_SHORT_VALUE, _XARGS_LONG_VALUE)
        if i >= len(argv):
            return [list(argv)]
        return unwrap_argv(argv[i:])
    return [list(argv)]


def scan_argv(argv):
    """Extract (action) candidates from a command's argv.

    argv[0] is the command itself and is not scanned: the gate checks
    what the command is asked to touch. Every later token is scanned:
    flags (leading '-') are skipped; a token containing '://' is a URL
    (host check); '--flag=value' contributes its value; anything else
    is treated as a path relative to the process working directory. A
    bare word that resolves inside the allowed scope is allowed.
    """
    actions = []
    for tok in argv[1:]:
        if tok.startswith("-"):
            if "=" in tok:
                _, _, value = tok.partition("=")
                if value:
                    actions.extend(_token_actions(value))
            continue
        actions.extend(_token_actions(tok))
    return actions


def _token_actions(tok):
    if "://" in tok:
        return [Action("network", tok)]
    return [Action("file_read", tok)]


def run_guarded(policy, log, argv, cwd=None, wall=True, confine=False,
                gate=None):
    """Pre-flight scan (tripwire): the command itself, then its
    arguments. Refuse (exit 2, no execution) on the first deny, else
    run the command inside the wall (unless wall is False, the
    explicit --no-wall opt-out) and return its exit code. When the
    wall cannot run here, or the definitions do not verify, refuse
    (exit 3) instead of running unprotected. Every decision is
    audited."""
    if confine:
        policy.mode = "confine"
    try:
        gate = gate or Gate(policy, log)
    except D.DefinitionsError as e:
        print(f"definitions: {e}")
        return EXIT_ERROR
    decision = gate.check_command(argv)
    if not decision.allowed:
        print(f"GATE: DENY — {decision.reason}"
              + (f" (rule {decision.rule})" if decision.rule else ""))
        print("refusing to run: " + " ".join(argv))
        return EXIT_DENY
    # Scan the unwrapped tokens too: `bash -c "cat /tmp/x/.env"`
    # names a protected file the outer argv never shows.
    for inner in unwrap_argv(argv):
        for action in scan_argv(inner):
            decision = gate.evaluate(action,
                                     note="pre-flight: " + " ".join(argv))
            if not decision.allowed:
                print(f"GATE: DENY — {decision.reason}"
                      + (f" (rule {decision.rule})" if decision.rule else ""))
                print("refusing to run: " + " ".join(argv))
                return EXIT_DENY
    if wall:
        import fineprint_wall as W
        try:
            return W.run_walled(policy, argv, log=log, cwd=cwd,
                                definitions=gate.definitions)
        except (W.WallUnavailable, D.DefinitionsError) as e:
            print(f"wall: {e}")
            return EXIT_ERROR
    print("wall: OFF (--no-wall) — tripwire only, not enforced "
          "(see docs/FREE_GATE.md)")
    try:
        proc = subprocess.run(argv, cwd=cwd)
    except FileNotFoundError as e:
        print(f"GATE: error — command not found: {e}")
        return EXIT_ERROR
    except Exception as e:  # noqa: BLE001
        print(f"GATE: error — {e}")
        return EXIT_ERROR
    if log is not None:
        log.append(Action("exec", " ".join(argv)),
                   Decision(True, f"ran, exit {proc.returncode}"),
                   note="executed")
    return proc.returncode


def default_policy():
    """Zero-config policy: ./fineprint-gate.json when it exists, else a
    built-in default — the PROTECTIVE DENYLIST (antivirus for agents:
    credential reads, destructive deletes, exfiltration of protected
    files, unapproved deploys, and the measured bypasses are blocked;
    normal work anywhere is allowed). The gate works with no flags;
    `fineprint init --gate` writes the file so the policy is visible
    and editable. Folder confinement is opt-in (--confine)."""
    local = Path.cwd() / "fineprint-gate.json"
    if local.exists():
        return Policy.from_file(local), f"policy: {local}"
    return Policy((".",), (), mode="deny"), (
        "policy: built-in default (protective denylist — normal work "
        "anywhere is allowed, known-dangerous patterns are blocked; "
        "see `fineprint gate definitions`) — run `fineprint init "
        "--gate` to save it as fineprint-gate.json")


def cmd_definitions():
    """Report the definitions version in force."""
    try:
        version, rules, source = D.load_definitions()
    except D.DefinitionsError as e:
        print(f"definitions: {e}")
        return EXIT_ERROR
    print(f"definitions: v{version} ({source})")
    print(f"rules: {len(rules)}")
    print(D.describe(rules))
    print("synthetic rules (tripwire only, not pack rules — not "
          "counted above):")
    print(D.describe(D.SYNTHETIC_RULES))
    print("update: a new pack ships with a FinePrint release "
          "(git pull, or a new release) — the wall verifies its "
          "signature before applying it.")
    return EXIT_ALLOW


def _render_log_entry(entry):
    """One readable line: tried X -> blocked by rule Y -> will always
    be blocked. Wall events render as what the wall did."""
    event = entry.get("event")
    if event == "WALL_START":
        return (f"wall up: {entry.get('mode', '?')} mode, definitions "
                f"{entry.get('definitions', '?')}, "
                f"{len(entry.get('hidden_paths', []))} hidden targets, "
                f"egress {entry.get('egress', '?')}")
    if event == "WALL_END":
        return f"wall down: {entry.get('note', '')}"
    if event == "WALL_PROXY_DENY":
        rule = entry.get("rule", "DENY-HOST")
        host = entry.get("action", {}).get("target", "?")
        return (f"tried {host} -> blocked by rule "
                f"{rule} -> will always be blocked")
    action = entry.get("action", {})
    target = action.get("target", "?")
    if entry.get("allowed"):
        return f"tried {target} -> allowed"
    rule = entry.get("rule")
    if rule:
        return (f"tried {target} -> blocked by rule {rule} -> "
                f"will always be blocked")
    return f"tried {target} -> blocked -> will always be blocked"


def cmd_log(log_path):
    """Render the audit log as readable notifications."""
    if not os.path.exists(log_path):
        print(f"gate log: no such file: {log_path}")
        return EXIT_ERROR
    ok = AuditLog.verify(log_path)
    entries = [json.loads(l) for l in Path(log_path).read_text().splitlines()
               if l.strip()]
    if not ok:
        print(f"audit log {log_path}: BROKEN — the hash chain does not "
              f"verify (entries below are untrusted)")
        return EXIT_DENY
    print(f"audit log {log_path}: valid ({len(entries)} entries)")
    for entry in entries:
        print(_render_log_entry(entry))
    return EXIT_ALLOW


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    policy = None
    policy_note = None
    log_path = None
    no_wall = False
    confine = False
    i = 0
    args = []
    while i < len(rest):
        if rest[i] == "--policy":
            policy = Policy.from_file(rest[i + 1])
            i += 2
        elif rest[i] == "--log":
            log_path = rest[i + 1]
            i += 2
        elif rest[i] == "--no-wall":
            no_wall = True
            i += 1
        elif rest[i] == "--confine":
            confine = True
            i += 1
        elif rest[i] == "--":
            args = rest[i + 1:]
            break
        else:
            args.append(rest[i])
            i += 1
    if cmd == "definitions":
        return cmd_definitions()
    if cmd == "log":
        if log_path is None:
            print("gate log: --log FILE is required")
            return EXIT_ERROR
        return cmd_log(log_path)
    if policy is None:
        policy, policy_note = default_policy()
        print(policy_note)
    if confine:
        policy.mode = "confine"
    log = AuditLog(log_path) if log_path else None
    try:
        gate = Gate(policy, log)
    except D.DefinitionsError as e:
        print(f"definitions: {e}")
        return EXIT_ERROR
    if cmd == "check":
        action = None
        j = 0
        while j < len(args):
            if args[j] == "--file":
                action = Action("file_read", args[j + 1])
                j += 2
            elif args[j] == "--host":
                action = Action("network", args[j + 1])
                j += 2
            else:
                print(f"gate check: unknown flag {args[j]!r}")
                return EXIT_ERROR
        if action is None:
            print("gate check: --file PATH or --host HOST is required")
            return EXIT_ERROR
        decision = gate.evaluate(action)
        print(f"GATE: {'ALLOW' if decision.allowed else 'DENY'} — "
              f"{decision.reason}"
              + (f" (rule {decision.rule})"
                 if not decision.allowed and decision.rule else ""))
        return EXIT_ALLOW if decision.allowed else EXIT_DENY
    if cmd == "run":
        if not args:
            print("gate run: a command is required after --")
            return EXIT_ERROR
        return run_guarded(policy, log, args, wall=not no_wall,
                           confine=confine, gate=gate)
    if cmd == "verify-log":
        if log_path is None:
            print("gate verify-log: --log FILE is required")
            return EXIT_ERROR
        if not os.path.exists(log_path):
            print(f"gate verify-log: no such file: {log_path}")
            return EXIT_ERROR
        ok = AuditLog.verify(log_path)
        print(f"audit log {log_path}: "
              f"{'valid' if ok else 'BROKEN — the hash chain does not verify'}")
        return EXIT_ALLOW if ok else EXIT_DENY
    print(f"gate: unknown subcommand {cmd!r}")
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
