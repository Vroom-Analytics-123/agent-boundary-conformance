#!/usr/bin/env python3
"""FinePrint definition packs — the antivirus-for-agents rule list.

The wall's default policy is a PROTECTIVE DENYLIST: it blocks
known-dangerous patterns derived from Catalogue v1 + our discovered
issues (credential reads, destructive deletes, exfiltration targets,
unapproved deploys, the bypasses we measured). Normal work anywhere
is allowed by default. Folder confinement (allowlist) is opt-in.

The denylist lives in versioned, SIGNED definition packs. The
built-in rules below are v1. A pack is a JSON file
`fineprint-definitions.json` with {"version", "rules", "signature"}:
the signature is Ed25519 over the canonical JSON of
{"version", "rules"}, made with the maintainers' key whose public
half is published in docs/SIGNING.md. The wall verifies the
signature before applying a pack and NEVER applies an unverified
one — a pack with no signature, a bad signature, or a signature
from the wrong key is refused, and the gate refuses to run rather
than silently using stale rules.

Update channel: the pack is a versioned file in the public repo /
release. Updating FinePrint (git pull, or a new release) brings the
new pack; the wall checks for it on every run and applies it when
it verifies. There is no live network update check.

Stdlib only (reuses tools/ed25519.py).
"""

import base64
import fnmatch
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ed25519  # noqa: E402

# The maintainers' public key, published in docs/SIGNING.md
# (fingerprint 0c0ab7b5e8fcff9caf21d4dcd3b28c094c69debf495325541548ead85b0b0e83).
DEFINITIONS_PUBLIC_KEY = bytes.fromhex(
    "40004a96827ae90e5ad4ae36da1414aa80d83625818668604803ba60f3393326")

BUILTIN_VERSION = "2026-11-07"

# Built-in v1 rules. kind "path": patterns are fnmatch globs on the
# full resolved path ("*" matches "/" too, so "**/.ssh" matches any
# .ssh directory at any depth). kind "command": "match" is the
# basename of argv[0] (exact) or a glob ("match_kind": "glob");
# "any_flag" means the rule fires only when one of those flags is
# present. kind "host": an exact host (case-insensitive).
# "reason" (Nov 8): why the rule is restricted. It is surfaced to
# the agent in the deny message and in `gate check` output, and in
# the app's policy screen — a rule the agent cannot understand is a
# rule it will keep testing. The field is OPTIONAL in a pack: older
# signed packs without it still verify (the signature covers the
# rules as listed), and the built-in v2026-11-07 rules all carry
# one. Adding the field does not change the pack version or the
# rule count (11).
BUILTIN_RULES = [
    {"id": "DENY-CRED-SSH", "kind": "path",
     "patterns": ["**/.ssh", "**/.ssh/**"],
     "description": "SSH private keys and config",
     "reason": "an SSH key lets the agent sign in as you on any host "
               "that trusts it"},
    {"id": "DENY-CRED-AWS", "kind": "path",
     "patterns": ["**/.aws", "**/.aws/**"],
     "description": "AWS credentials",
     "reason": "AWS credentials let the agent spend your money and "
               "read your cloud data"},
    {"id": "DENY-CRED-ENV", "kind": "path",
     "patterns": ["**/.env"],
     "description": ".env files (secrets)",
     "reason": ".env files hold app secrets and API keys"},
    {"id": "DENY-CRED-PEM", "kind": "path",
     "patterns": ["**/*key*.pem", "**/*private*.pem"],
     "description": "PEM private keys (key-named files; public CA "
                    "bundles such as cacert.pem are not matched)",
     "reason": "a PEM private key is a credential — whoever holds it "
               "can impersonate you"},
    {"id": "DENY-CRED-KEY", "kind": "path",
     "patterns": ["**/id_rsa*", "**/id_ed25519*"],
     "description": "SSH private key files",
     "reason": "an SSH private key lets the agent sign in as you"},
    {"id": "DENY-CRED-TOKEN", "kind": "path",
     "patterns": ["**/.git-credentials"],
     "description": "stored git credentials",
     "reason": "stored git credentials let the agent push and fetch "
               "as you"},
    {"id": "DENY-RECORDS", "kind": "path",
     "patterns": ["**/records.txt", "**/records/health"],
     "description": "the protected records file (FP-003)",
     "reason": "the records file is the protected data this boundary "
               "exists to keep from the agent"},
    {"id": "DENY-DELETE", "kind": "command",
     "match": "rm", "match_kind": "exact",
     "any_flag": ["-r", "-f", "-rf", "-fr", "-R",
                  "--recursive", "--force"],
     "description": "destructive delete (rm -r/-f)",
     "reason": "a recursive delete destroys work with no undo"},
    {"id": "DENY-SHRED", "kind": "command",
     "match": "shred", "match_kind": "exact",
     "description": "secure delete (shred)",
     "reason": "shred destroys data beyond recovery"},
    {"id": "DENY-UNLINK", "kind": "command",
     "match": "unlink", "match_kind": "exact",
     "description": "unlink — the bypass around the rm filter",
     "reason": "unlink deletes a file without the rm filter ever "
               "seeing it"},
    {"id": "DENY-DEPLOY", "kind": "command",
     "match": "*deploy*", "match_kind": "glob",
     "description": "unapproved deploy (a command named *deploy*)",
     "reason": "a deploy ships code to production"},
]


# Synthetic tripwire rules (F2): rule ids the tripwire itself emits
# that are NOT pack rules. DENY-EXFIL fires when a copy/send command
# (cp/scp/rsync/curl/wget) names a protected file — a composite check
# (command + protected path) the pack schema cannot express as one
# rule. The id is declared here, in the definitions module, so the
# proof's evidence never cites a rule id that lives nowhere, and
# `gate definitions` prints it under "synthetic rules" so it is in
# the definitions in force as printed. It is NOT counted in the
# pack's rule count and does NOT change the pack version (the app's
# real-CLI tests pin both: 11 rules, v2026-11-07).
DENY_EXFIL_ID = "DENY-EXFIL"

SYNTHETIC_RULES = [
    {"id": DENY_EXFIL_ID, "kind": "synthetic",
     "description": "copy/send of a protected file (tripwire only)",
     "reason": "copying a protected file out is how secrets leave "
               "the machine"},
]


class DefinitionsError(Exception):
    """A definitions pack was present but could not be verified."""


def builtin_rules():
    """The built-in v1 rules (a copy, so callers cannot mutate them)."""
    return [dict(r, patterns=list(r.get("patterns", [])))
            if "patterns" in r else dict(r) for r in BUILTIN_RULES]


def canonical_bytes(version, rules):
    return json.dumps({"version": version, "rules": rules},
                      sort_keys=True, separators=(",", ":")).encode()


def verify_pack(pack, public_key=DEFINITIONS_PUBLIC_KEY):
    """True only when the pack carries a valid signature from the key."""
    sig_b64 = pack.get("signature")
    if not sig_b64:
        return False
    try:
        sig = base64.b64decode(sig_b64)
    except Exception:
        return False
    return ed25519.checkvalid(
        sig, canonical_bytes(pack["version"], pack["rules"]), public_key)


def _pack_search_paths(search_paths=None):
    if search_paths is not None:
        return [Path(p) / "fineprint-definitions.json"
                for p in search_paths]
    paths = [Path.cwd() / "fineprint-definitions.json",
             Path(__file__).resolve().parent.parent / "definitions"
             / "fineprint-definitions.json"]
    return paths


def load_definitions(public_key=DEFINITIONS_PUBLIC_KEY,
                     search_paths=None):
    """Return (version, rules, source).

    No pack file found -> the built-in v1 rules, source "built-in".
    A pack file found -> it must verify, or DefinitionsError is raised
    (never apply an unverified pack)."""
    for path in _pack_search_paths(search_paths):
        if not path.exists():
            continue
        try:
            pack = json.loads(path.read_text())
        except Exception as e:  # noqa: BLE001
            raise DefinitionsError(
                f"definitions pack {path} is not valid JSON: {e}")
        if not verify_pack(pack, public_key):
            raise DefinitionsError(
                f"definitions pack {path} does not verify "
                f"(missing, bad, or wrong-key signature) — refusing to "
                f"apply it. Delete it or replace it with a signed pack "
                f"from a FinePrint release.")
        return pack["version"], pack["rules"], str(path)
    return BUILTIN_VERSION, builtin_rules(), "built-in"


def path_rule(path, rules):
    """The id of the first path rule matching this resolved path, else None."""
    for rule in rules:
        if rule.get("kind") != "path":
            continue
        for pattern in rule.get("patterns", []):
            if fnmatch.fnmatch(path, pattern):
                return rule["id"]
    return None


def host_rule(host, rules):
    """The id of the first host rule matching this host, else None."""
    host = host.lower()
    for rule in rules:
        if rule.get("kind") != "host":
            continue
        if host == rule.get("match", "").lower():
            return rule["id"]
    return None


def command_rule(argv, rules):
    """The id of the first command rule matching argv, else None.

    Matches on the basename of argv[0]. A rule with "any_flag" fires
    only when one of those flags appears in argv."""
    if not argv:
        return None
    base = os.path.basename(argv[0])
    flags = set(argv[1:])
    for rule in rules:
        if rule.get("kind") != "command":
            continue
        match = rule.get("match", "")
        kind = rule.get("match_kind", "exact")
        hit = (fnmatch.fnmatch(base, match) if kind == "glob"
               else base == match)
        if not hit:
            continue
        any_flag = rule.get("any_flag")
        if any_flag and not (flags & set(any_flag)):
            continue
        return rule["id"]
    return None


def describe(rules):
    """One line per rule: id, kind, description — and the reason
    when the rule carries one (all built-in v2026-11-07 rules do;
    older signed packs may not)."""
    lines = []
    for rule in rules:
        line = (f"  {rule['id']:<16} {rule.get('kind', ''):<8} "
                f"{rule.get('description', '')}")
        reason = rule.get("reason")
        if reason:
            line += f" — {reason}"
        lines.append(line)
    return "\n".join(lines)
