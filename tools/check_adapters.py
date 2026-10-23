#!/usr/bin/env python3
"""Harness adapters for tools/fineprint_check.py.

Adapter contract (see docs/CATALOGUE_COMMONS.md, "Adapter contract"):
  check_environment() -> (ok: bool, detail: str)
      Is this adapter runnable on this machine right now?
  run_probe(argv, policy) -> dict with keys:
      actual         one of forbidden|prompt|allow|unknown|error
      matched_rules  int (codex) or dict (reconstructed engines); informational
      raw            raw native output (codex) or "" (reconstructed)
      note           human-readable evidence note
      layer          "rules-layer" (codex, vendor-confirmed) or "rules"
                     (reconstructed engines)
      error          None, or a string when actual == "error"

Registered adapters (measurement routes are provenance of the Layer-1
measurement only — unranked, never harness quality; founder correction
2026-10-22):
  codex        vendor-confirmed — the pinned native oracle
               (codex execpolicy check) via tools/pin.py. Fail closed: if
               the pinned binary is unavailable or its sha256 mismatches,
               check_environment() reports not-ok and the runner refuses
               to fabricate results.
  claude-code  reconstructed — the documented-semantics evaluation engine
               at adapters/claude-code/evaluate.py. Labelled
               reimplementation of the vendor's documented matching
               semantics; NEVER interrogates a native oracle (none
               exists). Evidence class "reconstructed-evaluation (never
               interrogated)".

Other T2 engines (cursor, gemini-cli, opencode) expose different
evaluate() signatures today; they are registered here only when a shim
conforming to this contract exists. Registering a wrong shim would be
worse than no adapter.

Stdlib only (the claude-code engine import is in-repo).
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import schemas_v1 as S  # noqa: E402
from pin import PINNED_CODEX_SHA256, PINNED_CODEX_VERSION  # noqa: E402

LAYER_ATTRIBUTION = ("no rules-layer decision; runtime outcome depends on "
                     "approval policy + sandbox under the pinned "
                     "configuration")

EVIDENCE_CLASS_VENDOR_CONFIRMED = "REPRO"
EVIDENCE_CLASS_RECONSTRUCTED = "reconstructed-evaluation (never interrogated)"


# --------------------------------------------------------------------------
# codex (vendor-confirmed, pinned native oracle)
# --------------------------------------------------------------------------

def codex_binary():
    """Resolve the pinned oracle, fail closed (tools/pin.py)."""
    from pin import codex_binary as _resolve
    return _resolve()


def codex_check_environment():
    try:
        binary = codex_binary()
    except RuntimeError as e:
        return False, f"pinned oracle unavailable: {e}"
    try:
        proc = subprocess.run([str(binary), "--version"], capture_output=True,
                              text=True, timeout=60)
        detected = proc.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return False, f"pinned binary would not run: {e}"
    if PINNED_CODEX_VERSION not in detected:
        return False, (f"version drift: pinned {PINNED_CODEX_VERSION}, "
                       f"binary reports {detected!r}")
    return True, (f"pinned oracle ok: {detected} "
                  f"(sha256 {PINNED_CODEX_SHA256[:16]}…)")


def codex_run_probe(argv, policy):
    binary = codex_binary()
    cmd = [str(binary), "execpolicy", "check", "--rules", str(policy),
           "--", *argv]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=300)
    except Exception as e:  # noqa: BLE001
        return {"actual": "error", "matched_rules": 0, "raw": "",
                "note": f"oracle execution failed: {e}",
                "layer": "rules-layer", "error": str(e)}
    raw = proc.stdout.strip()
    ser = S.serialize_native_decision(raw)
    note = ""
    if ser["decision"] == "unknown":
        note = LAYER_ATTRIBUTION
    return {"actual": ser["decision"],
            "matched_rules": ser["matched_rules_count"],
            "raw": raw, "note": note, "layer": "rules-layer", "error": None}


# --------------------------------------------------------------------------
# claude-code (reconstructed, documented-semantics engine)
# --------------------------------------------------------------------------

def _claude_engine():
    sys.path.insert(0, str(REPO / "adapters" / "claude-code"))
    import evaluate  # noqa: E402
    return evaluate


def claude_code_check_environment():
    try:
        engine = _claude_engine()
    except Exception as e:  # noqa: BLE001
        return False, f"engine import failed: {e}"
    if not hasattr(engine, "evaluate"):
        return False, "engine has no evaluate()"
    return True, ("engine ok: adapters/claude-code/evaluate.py "
                  "(documented semantics, never interrogated)")


def claude_code_run_probe(argv, policy):
    engine = _claude_engine()
    try:
        permissions = json.loads(Path(policy).read_text())["permissions"]
    except Exception as e:  # noqa: BLE001
        return {"actual": "error", "matched_rules": 0, "raw": "",
                "note": f"policy read failed: {e}", "layer": "rules",
                "error": str(e)}
    command = " ".join(argv)
    try:
        res = engine.evaluate(command, permissions)
    except Exception as e:  # noqa: BLE001
        return {"actual": "error", "matched_rules": 0, "raw": "",
                "note": f"engine failed: {e}", "layer": "rules",
                "error": str(e)}
    decision = res.get("decision")
    if decision not in ("forbidden", "prompt", "allow", "unknown"):
        return {"actual": "error", "matched_rules": 0, "raw": "",
                "note": f"engine returned out-of-vocabulary decision "
                        f"{decision!r}", "layer": "rules",
                "error": "bad decision vocabulary"}
    note = res.get("note", "")
    if decision == "unknown" and "no rules-layer decision" not in note:
        note = (note + " " if note else "") + LAYER_ATTRIBUTION
    return {"actual": decision, "matched_rules": res.get("matched_rules", {}),
            "raw": "", "note": note, "layer": "rules", "error": None}


ADAPTERS = {
    "codex": {
        "measurement_route": "vendor-confirmed",
        "evidence_class": EVIDENCE_CLASS_VENDOR_CONFIRMED,
        "has_decision_source": True,
        "policy_kind": "codex .rules file (execpolicy Starlark prefix_rule)",
        "check_environment": codex_check_environment,
        "run_probe": codex_run_probe,
    },
    "claude-code": {
        "measurement_route": "reconstructed",
        "evidence_class": EVIDENCE_CLASS_RECONSTRUCTED,
        "has_decision_source": True,
        "policy_kind": "Claude Code settings JSON with a 'permissions' object",
        "check_environment": claude_code_check_environment,
        "run_probe": claude_code_run_probe,
    },
}


def list_adapters():
    return {name: {"measurement_route": a["measurement_route"],
                   "evidence_class": a["evidence_class"],
                   "policy_kind": a["policy_kind"]}
            for name, a in ADAPTERS.items()}
