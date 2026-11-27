#!/usr/bin/env python3
"""FinePrint free gate: a wrapper-level guard for local + CI use.

Adapted from the paid-product prototype's decision logic
(program repo, paid-product/gate.py) with one hardening the prototype
lacked: path decisions run on the REALPATH (symlinks resolved), so a
symlink inside an allowed directory that points outside is denied.
The audit log is the prototype's hash-chained JSONL design, unchanged
in shape.

What this is: a tripwire + audit trail for the common paths. `gate run`
pre-flights a command's arguments, refuses to run it when an argument
names a path outside the allowed scope or a host outside the allowlist,
and records every decision. `gate check` answers one allow/deny question.

What this is NOT (read docs/FREE_GATE.md before trusting it):
  - NOT a sandbox. It does not intercept syscalls. A command can still
    read a file it does not name on argv (a script, an env var, a config
    file), follow a symlink created after the check (TOCTOU), or exfiltrate
    over a host that never appears in argv.
  - NOT production enforcement. The hardened gate (sandbox + egress proxy
    + filesystem boundary) is the paid product; this wrapper stops the
    common paths and proves the decision was recorded.
  - A bare word that resolves inside the allowed scope is allowed: the
    gate checks what a command is asked to touch, not what it might do.
    `gate run` takes argv directly (no shell), so shell redirections
    cannot even be expressed through it.

Deny-by-default: anything not explicitly allowed is denied. Unknown
action kinds are denied. A decision is never silently allow.

Stdlib only. Usage:
  python3 tools/fineprint_gate.py check --file PATH --policy FILE
  python3 tools/fineprint_gate.py check --host HOST --policy FILE
  python3 tools/fineprint_gate.py run --policy FILE [--log FILE] -- CMD...
  (the `fineprint` CLI wraps these; see `fineprint gate --help`)
"""

import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

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


def _realpath(path):
    """Resolve symlinks + .. segments. Non-existent tails are kept."""
    return os.path.realpath(path)


class Policy:
    """Deny-by-default. Paths are checked on their realpath; hosts are
    matched exactly (case-insensitive)."""

    def __init__(self, allowed_paths=(), allowed_hosts=()):
        self.allowed_paths = tuple(
            _realpath(p) for p in allowed_paths)
        self.allowed_hosts = tuple(h.lower() for h in allowed_hosts)

    @classmethod
    def from_file(cls, path):
        doc = json.loads(Path(path).read_text())
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: policy must be a JSON object")
        return cls(doc.get("allowed_paths", ()),
                   doc.get("allowed_hosts", ()))

    @classmethod
    def from_dict(cls, doc):
        return cls(doc.get("allowed_paths", ()),
                   doc.get("allowed_hosts", ()))

    def decide(self, action):
        if action.kind in ("file_read", "file_write"):
            target = action.target
            if ".." in Path(target).parts:
                return Decision(False, "path traversal rejected: "
                                       f"{target!r} contains '..'")
            real = _realpath(target)
            for prefix in self.allowed_paths:
                if real == prefix or real.startswith(prefix.rstrip(os.sep)
                                                     + os.sep):
                    return Decision(
                        True, f"{action.kind} under allowed path {prefix}")
            return Decision(False, f"{action.kind} outside allowed paths: "
                                   f"{target!r} resolves to {real!r}")
        if action.kind == "network":
            host = _host_of(action.target)
            if host in self.allowed_hosts:
                return Decision(True, f"host {host} allowlisted")
            return Decision(False, f"host {host} not allowlisted")
        return Decision(False, f"unknown action kind {action.kind!r}")


def _host_of(target):
    """A bare hostname, or the host of an http(s) URL."""
    if "://" in target:
        return (urllib.parse.urlparse(target).hostname or "").lower()
    return target.lower().split("/")[0].split(":")[0]


class AuditLog:
    """Append-only JSONL log. Each entry hashes the previous entry's hash,
    so any edit to an earlier entry breaks verification of everything
    after. Same shape as the paid-product prototype's log."""

    def __init__(self, path):
        self.path = path
        self.prev_hash = "0" * 64
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path) as f:
                for line in f:
                    if line.strip():
                        self.prev_hash = json.loads(line)["hash"]

    def append(self, action, decision, note=""):
        entry = {
            "action": {"kind": action.kind, "target": action.target},
            "allowed": decision.allowed,
            "reason": decision.reason,
            "note": note,
            "prev_hash": self.prev_hash,
        }
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
    def __init__(self, policy, log=None):
        self.policy = policy
        self.log = log

    def evaluate(self, action, note=""):
        decision = self.policy.decide(action)
        if self.log is not None:
            self.log.append(action, decision, note=note)
        return decision


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


def run_guarded(policy, log, argv, cwd=None):
    """Pre-flight scan; refuse (exit 2, no execution) on the first deny,
    else run the command with argv directly (no shell) and return its
    exit code. Every decision is audited."""
    gate = Gate(policy, log)
    for action in scan_argv(argv):
        decision = gate.evaluate(action, note="pre-flight: " + " ".join(argv))
        if not decision.allowed:
            print(f"GATE: DENY — {decision.reason}")
            print("refusing to run: " + " ".join(argv))
            return EXIT_DENY
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
    built-in default (this directory only, no hosts). The gate works
    with no flags; `fineprint init --gate` writes the file so the
    policy is visible and editable."""
    local = Path.cwd() / "fineprint-gate.json"
    if local.exists():
        return Policy.from_file(local), f"policy: {local}"
    return Policy((str(Path.cwd()),), ()), (
        "policy: built-in default (this directory only, no hosts) — "
        "run `fineprint init --gate` to save it as fineprint-gate.json")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    policy = None
    policy_note = None
    log_path = None
    i = 0
    args = []
    while i < len(rest):
        if rest[i] == "--policy":
            policy = Policy.from_file(rest[i + 1])
            i += 2
        elif rest[i] == "--log":
            log_path = rest[i + 1]
            i += 2
        elif rest[i] == "--":
            args = rest[i + 1:]
            break
        else:
            args.append(rest[i])
            i += 1
    if policy is None:
        policy, policy_note = default_policy()
        print(policy_note)
    log = AuditLog(log_path) if log_path else None
    gate = Gate(policy, log)
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
              f"{decision.reason}")
        return EXIT_ALLOW if decision.allowed else EXIT_DENY
    if cmd == "run":
        if not args:
            print("gate run: a command is required after --")
            return EXIT_ERROR
        return run_guarded(policy, log, args)
    print(f"gate: unknown subcommand {cmd!r}")
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
