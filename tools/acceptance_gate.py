#!/usr/bin/env python3
"""Gate helpers for the acceptance campaign — pure functions over the
`fineprint gate` CLI (branch free-wall).

The campaign wraps the Cursor agent CLI in `fineprint gate run`, so it
needs to (a) build the gate command without ever passing --no-wall,
(b) read the gate's audit log back (WALL_START carries the boundary
that was actually in force — mode, definitions version, hidden paths,
allowed/denied hosts, egress — and any tripwire denial carries its
rule id), and (c) run the fail-closed pre-checks (`gate probe`,
`gate definitions`, `gate verify-log`).

Stdlib only. No Cursor, no network, no secrets: the gate script path
and the checkout are the only inputs, and the functions never read a
credential value.

The one hard rule in this module: --no-wall is never emitted. It is a
debugging opt-out, and the proof run must never use it. gate_argv
asserts it.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

GATE_REL = Path("tools") / "fineprint_gate.py"
WALL_REL = Path("tools") / "fineprint_wall.py"

EXIT_ALLOW = 0
EXIT_DENY = 2
EXIT_ERROR = 3


class GateError(Exception):
    """The gate checkout is unusable or a gate subcommand failed."""


def find_gate(checkout):
    """Resolve the gate script in a fineprint checkout.

    Returns {"gate": Path, "wall": Path, "checkout": Path,
    "head": str|None}. Raises GateError when the checkout has no gate
    script, or no wall module (free-check-gate has no wall — the gate
    refuses to run a guarded command there, and the campaign must say
    so instead of failing mid-run). The head is the checkout's git
    HEAD when it is a git checkout, else None (never a guess).
    """
    checkout = Path(checkout)
    gate = checkout / GATE_REL
    wall = checkout / WALL_REL
    if not gate.is_file():
        raise GateError(
            f"no gate script at {gate} — expected a fineprint "
            f"checkout (branch free-wall) at {checkout}")
    if not wall.is_file():
        raise GateError(
            f"no wall module at {wall} — this checkout has no wall "
            f"(free-check-gate has no wall module); the campaign "
            f"needs branch free-wall")
    head = None
    try:
        r = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            head = r.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        head = None
    return {"gate": gate, "wall": wall, "checkout": checkout,
            "head": head}


def gate_argv(gate_script, *, mode, policy_path, log_path, agent_argv,
              python=None):
    """The full argv for one gated agent invocation.

    mode "deny" (the default) is the protective denylist; mode
    "confine" adds --confine (the folder allowlist + the egress
    allowlist from the policy). --no-wall is never added — the proof
    run must never run tripwire-only. The agent command follows the
    "--" separator, exactly as `fineprint gate run` takes it.
    """
    if mode not in ("deny", "confine"):
        raise ValueError(f"unknown gate mode {mode!r} (deny|confine)")
    if not agent_argv:
        raise ValueError("gate_argv needs the agent command")
    py = python or sys.executable
    argv = [py, str(gate_script), "run",
            "--policy", str(policy_path),
            "--log", str(log_path)]
    if mode == "confine":
        argv.append("--confine")
    argv += ["--", *agent_argv]
    return argv


def run_gate(gate_script, args, *, python=None, timeout=120):
    """Run one gate subcommand; return (exit_code, stdout, stderr).

    Never raises on a non-zero exit (a deny is exit 2, a refusal is
    exit 3 — both are data, not crashes). Raises GateError only when
    the gate script cannot be started at all.
    """
    py = python or sys.executable
    try:
        r = subprocess.run(
            [py, str(gate_script), *args],
            capture_output=True, text=True, timeout=timeout)
    except OSError as exc:
        raise GateError(f"cannot start the gate script: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise GateError(
            f"gate subcommand timed out after {timeout}s: {args}") from exc
    return r.returncode, r.stdout, r.stderr


def parse_definitions_output(text):
    """(version, rule_count) from `gate definitions` output.

    The output's first line is "definitions: v2026-11-07 (built-in)"
    and the second is "rules: 11". Anything else is a parse failure
    (the campaign records it, it never guesses a version).
    """
    version = None
    count = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("definitions: v"):
            version = line.split("definitions: v", 1)[1].split()[0]
        elif line.startswith("rules:"):
            try:
                count = int(line.split("rules:", 1)[1].strip())
            except ValueError:
                count = None
    if version is None or count is None:
        raise GateError(
            "cannot parse `gate definitions` output — the definitions "
            f"in force are unknown:\n{text}")
    return version, count


def verify_chain(entries):
    """Re-derive the hash chain over parsed log entries.

    Each entry hashes the previous entry's hash (sha256 over the
    canonical JSON of the entry without its own "hash" field). The
    first entry's prev_hash is 64 zeroes. Returns a list of problem
    strings (empty = the chain verifies). This is the same check
    `gate verify-log` performs; the campaign runs both (this one so
    the verdict layer can name the broken entry, the gate's so the
    evidence carries the gate's own verdict).
    """
    problems = []
    prev = "0" * 64
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"entry {i}: not an object")
            continue
        h = entry.get("hash")
        if entry.get("prev_hash") != prev:
            problems.append(
                f"entry {i}: prev_hash does not match the previous "
                f"entry's hash")
        body = {k: v for k, v in entry.items() if k != "hash"}
        blob = json.dumps(body, sort_keys=True).encode()
        if h != hashlib.sha256(blob).hexdigest():
            problems.append(f"entry {i}: hash does not re-derive")
        prev = h if isinstance(h, str) else prev
    return problems


def read_gate_log(log_path):
    """Parse a gate audit log (JSONL) into its evidence.

    Returns {"entries", "denials", "wall_start", "wall_end",
    "proxy_denials", "problems", "chain_problems"}:
    - entries: every parsed entry, in order.
    - denials: entries with allowed == False and a "rule" (a tripwire
      or second-opinion denial — the wall's hiding logs no denial
      entry, it logs WALL_START with the hidden paths).
    - wall_start / wall_end: the WALL_START / WALL_END entries (or
      None when the wall never started — a gate that refused at
      pre-flight has no WALL_START, which is itself evidence).
    - proxy_denials: WALL_PROXY_DENY entries (the egress block
      firing in confine mode with hosts allowlisted).
    - problems: unparseable lines (never silently skipped).
    - chain_problems: hash-chain verification failures (see
      verify_chain).
    """
    log_path = Path(log_path)
    entries = []
    problems = []
    if not log_path.exists():
        return {"entries": entries, "denials": [], "wall_start": None,
                "wall_end": None, "proxy_denials": [], "problems":
                [f"no such log file: {log_path}"],
                "chain_problems": ["log file missing"]}
    for i, line in enumerate(log_path.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            problems.append(f"line {i + 1}: not JSON ({exc})")
    denials = [e for e in entries
               if e.get("allowed") is False and e.get("rule")]
    wall_start = next((e for e in entries
                       if e.get("event") == "WALL_START"), None)
    wall_end = next((e for e in entries
                     if e.get("event") == "WALL_END"), None)
    proxy_denials = [e for e in entries
                     if e.get("event") == "WALL_PROXY_DENY"]
    return {"entries": entries, "denials": denials,
            "wall_start": wall_start, "wall_end": wall_end,
            "proxy_denials": proxy_denials, "problems": problems,
            "chain_problems": verify_chain(entries)}


def wall_hidden_paths(wall_start):
    """The hidden_paths list from a WALL_START entry (or [])."""
    if not wall_start:
        return []
    hidden = wall_start.get("hidden_paths") or []
    return [str(p) for p in hidden]


def wall_definitions(wall_start):
    """The definitions string from a WALL_START entry (or None)."""
    if not wall_start:
        return None
    return wall_start.get("definitions")
