#!/usr/bin/env python3
"""Amp T1 oracle runner for the full 41-case corpus + protected family.

Runs every corpus fixture (fixtures/fixtures.json — public + held-out shards)
and the protected family (fixtures/protected_records_public.json +
fixtures/protected_records_heldout.json when present) through the pinned Amp
binary's native decision oracle:

    amp permissions test --json Bash --cmd "<argv joined>" --settings-file <policy>

Each fixture's `rules` file maps to the Amp ingestion of that policy:
  fixtures/policies/default.rules            -> adapters/amp/policy/corpus.json
  fixtures/policies/protected_records.rules  -> adapters/amp/policy/protected.json

Command strings are joined as-written (" ".join(argv)) — Amp's oracle matches
the cmd string verbatim (globs/regex), the same as-written semantics the
spike verified (REPRO). There is no resolve_host_executables analogue in Amp;
path-form fixtures (F-13R, F-14R, F-14bR, F-13d) are measured as-written and
recorded as observed.

Safety: fresh scratch HOME/AMP_HOME (no credentials), vendored binary only
(sha256-verified against the pin), 60s timeout per probe, no login, no model,
no agent session.

Output: a rerun doc at evidence/amp-2026-10-22/rerun.json carrying per-case
raw oracle JSON for run1 AND run2, with byte-identical determinism verified
on the raw stdout. Stdlib only.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

AMP_BINARY = REPO / "tools/vendor/amp/0.0.1792680614-g8973a3/bin/amp"
PINNED_AMP_VERSION = "0.0.1792680614-g8973a3"
PINNED_AMP_SHA256 = "89304a6e5bc739807062433a28bba5a98dc8dfbae05d8674df06a465103c8f3f"

FIXTURES = REPO / "fixtures" / "fixtures.json"
MANIFEST = REPO / "fixtures" / "corpus_manifest.json"
PROT_PUBLIC = REPO / "fixtures" / "protected_records_public.json"
PROT_HELDOUT = REPO / "fixtures" / "protected_records_heldout.json"
NEG_CONTROLS = REPO / "fixtures" / "negative_controls.json"

POLICY_MAP = {
    "fixtures/policies/default.rules": REPO / "adapters" / "amp" / "policy" / "corpus.json",
    "fixtures/policies/protected_records.rules": REPO / "adapters" / "amp" / "policy" / "protected.json",
}
# Precedence fixtures (F-15a..f) ingest the prec_*.rules policies into Amp's
# list-ordered amp.permissions entries, preserving rule order so Amp's own
# first-match-wins precedence is what gets measured (contrast with Codex's
# most-restrictive-wins — the sharpest inter-harness difference).
for _sfx in ("a", "b", "c", "d", "e", "f"):
    POLICY_MAP[f"evidence/day1-baseline-2026-10-21/prec_{_sfx}.rules"] = (
        REPO / "adapters" / "amp" / "policy" / f"prec_{_sfx}.json")

AMP_TO_FRAMEWORK = {"allow": "allow", "ask": "prompt", "reject": "forbidden",
                    None: "unknown", "delegate": "unmapped"}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_env():
    scratch = Path(tempfile.mkdtemp(prefix="amp-run-"))
    fakehome = scratch / "fakehome"
    amphome = scratch / "amp-home"
    fakehome.mkdir()
    amphome.mkdir()
    env = dict(os.environ)
    for k in ("AMP_API_KEY", "AMP_URL"):
        env.pop(k, None)
    env["HOME"] = str(fakehome)
    env["AMP_HOME"] = str(amphome)
    env["XDG_CONFIG_HOME"] = str(fakehome / ".config")
    env["XDG_DATA_HOME"] = str(fakehome / ".local" / "share")
    return env


def oracle_call(cmd_str, policy_path, env):
    cmd = [str(AMP_BINARY), "--settings-file", str(policy_path),
           "permissions", "test", "--json", "Bash", "--cmd", cmd_str]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode


def load_cases():
    fixtures_doc = json.loads(FIXTURES.read_text())
    cases = [("corpus", f) for f in fixtures_doc["fixtures"]]
    prot_pub = json.loads(PROT_PUBLIC.read_text())
    cases += [("protected-public", f) for f in prot_pub["fixtures"]]
    if PROT_HELDOUT.exists():
        prot_held = json.loads(PROT_HELDOUT.read_text())
        cases += [("protected-heldout", f) for f in prot_held["fixtures"]]
    else:
        print("note: no protected heldout file; family = public shard only", file=sys.stderr)
    neg_doc = json.loads(NEG_CONTROLS.read_text())
    controls = neg_doc["controls"]
    return cases, controls


def main():
    digest = sha256_file(AMP_BINARY)
    if digest != PINNED_AMP_SHA256:
        sys.exit(f"amp binary drift: {digest} != pinned {PINNED_AMP_SHA256}")
    ver = subprocess.run([str(AMP_BINARY), "--version"], capture_output=True,
                         text=True, timeout=30, env=make_env())
    print("oracle:", ver.stdout.strip(), file=sys.stderr)

    cases, controls = load_cases()
    env = make_env()
    problems = []
    out_cases = []
    out_controls = []

    def probe(cmd_str, policy_path):
        runs = []
        for _ in (1, 2):
            stdout, stderr, rc = oracle_call(cmd_str, policy_path, env)
            runs.append({"stdout": stdout, "stderr": stderr[-400:] if stderr else "",
                         "returncode": rc})
        if runs[0]["stdout"] != runs[1]["stdout"]:
            problems.append(f"non-deterministic: {cmd_str!r}")
        return runs

    for family, f in cases:
        fid = f["id"]
        cmd_str = " ".join(f["argv"])
        policy_path = POLICY_MAP[f["rules"]]
        runs = probe(cmd_str, policy_path)
        try:
            parsed = json.loads(runs[0]["stdout"])
            action = parsed.get("action")
        except Exception as e:  # noqa: BLE001
            problems.append(f"unparseable output for {fid}: {e}")
            parsed, action = {}, None
        out_cases.append({
            "family": family,
            "fixture_id": fid,
            "shard": "held-out" if "heldout" in family or fid not in json.loads(MANIFEST.read_text())["public"]["fixture_ids"] and family == "corpus" else "public",
            "argv": f["argv"],
            "command_string": cmd_str,
            "corpus_rules": f["rules"],
            "policy_file": str(policy_path.relative_to(REPO)),
            "expected": f.get("expected"),
            "maps_to": f.get("maps_to"),
            "run1": runs[0],
            "run2": runs[1],
            "parsed": parsed,
            "framework_decision": AMP_TO_FRAMEWORK.get(action, f"unmapped:{action}"),
        })

    for c in controls:
        cmd_str = " ".join(c["argv"])
        policy_path = POLICY_MAP[c["rules"]]
        runs = probe(cmd_str, policy_path)
        try:
            action = json.loads(runs[0]["stdout"]).get("action")
        except Exception:  # noqa: BLE001
            action = None
        out_controls.append({
            "control_id": c["control_id"], "kind": c.get("kind"),
            "argv": c["argv"], "command_string": cmd_str,
            "expected": c.get("expected"),
            "framework_decision": AMP_TO_FRAMEWORK.get(action, f"unmapped:{action}"),
            "raw_action": action,
        })

    # held-out shard ids: fixtures whose id is not in the public list (corpus),
    # plus the protected-heldout family.
    pub_ids = set(json.loads(MANIFEST.read_text())["public"]["fixture_ids"])
    for o in out_cases:
        if o["family"] == "corpus":
            o["shard"] = "public" if o["fixture_id"] in pub_ids else "held-out"
        elif o["family"] == "protected-heldout":
            o["shard"] = "held-out"
        else:
            o["shard"] = "public"

    out_dir = REPO / "evidence" / "amp-2026-10-22"
    out_dir.mkdir(parents=True, exist_ok=True)
    rerun = {
        "schema_version": "amp-rerun.v1",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pinned": {
            "amp_version": PINNED_AMP_VERSION,
            "amp_version_detected": ver.stdout.strip(),
            "binary_path": str(AMP_BINARY.relative_to(REPO)),
            "binary_sha256": digest,
            "corpus_version_hash": json.loads(MANIFEST.read_text())["corpus_version_hash"],
            "policy_sha256": {str(p.relative_to(REPO)): sha256_file(p) for p in set(POLICY_MAP.values())},
        },
        "determinism": {"runs": 2, "byte_identical": len(problems) == 0, "problems": problems},
        "cases": out_cases,
        "negative_controls": out_controls,
    }
    path = out_dir / "rerun.json"
    path.write_text(json.dumps(rerun, indent=2, sort_keys=True))
    print(f"wrote {path} ({len(out_cases)} cases, {len(out_controls)} controls)", file=sys.stderr)
    print(f"byte-identical: {len(problems) == 0}", file=sys.stderr)
    if problems:
        print("PROBLEMS:", *problems, sep="\n  ", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
