#!/usr/bin/env python3
"""Copilot CLI driver for the live runner — the pilot harness.

Reuses the sealed Nov 4 full-matrix runner WITHOUT rewriting it:
framework/scorecard/copilot-full-v1/runners/full_runner.py supplies
FULL_TASKS (24 variants) and run_cell() (per-cell invocation,
fixtures, harm evaluation, record writing). This driver is a thin
adapter: it translates the legacy record into the framework's
CellResult shape and adds the one thing the legacy record lacks —
the model actually observed, parsed from the CLI's JSONL stdout
(model fields, modelCacheState modelId, modelMetrics keys).

Approval-mode honesty (from the legacy runner, binding): the
non-interactive -p invocation REQUIRES --allow-all-tools, so this
matrix does NOT measure native interactive ask/deny dialog behavior.
The only configured permission signal is the --deny-tool rule
shell(rm:*), which covers rm-stem commands ONLY. A deny-rule marker
on a non-deletion cell means the output contained denial wording,
NOT that a configured rule fired — so deny_rule_id is reported only
when deny_rule_covers is true; otherwise it is None, never invented.

Model note: the model is NOT pinned for Copilot (the CLI chooses its
default). model_observed is whatever the stdout metrics name, per
cell; when the stdout names zero models or more than one, the model
is "unobserved" (candidates listed) rather than guessed.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from live_drivers.base import BaseDriver

REPO = Path(__file__).resolve().parent.parent.parent
_RUNNERS = (REPO / "framework" / "scorecard" / "copilot-full-v1"
            / "runners")
sys.path.insert(0, str(_RUNNERS))

import full_runner as legacy  # noqa: E402

DENY_RULE = "shell(rm:*)"
TOKEN_NAMES = ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")


def _extract_model(stdout_log: Path):
    """Parse Copilot JSONL stdout for the model(s) actually used.

    Returns (model_observed, source, candidates). Exactly one
    distinct model -> observed via stdout-metrics. Zero or several
    -> unobserved (candidates listed, never guessed).
    """
    models = set()
    if not stdout_log.exists():
        return None, "unobserved", []
    try:
        for line in stdout_log.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj.get("model"), str):
                models.add(obj["model"])
            data = obj.get("data") or {}
            if isinstance(data, dict):
                metrics = data.get("modelMetrics")
                if isinstance(metrics, dict):
                    models.update(metrics.keys())
                cache = data.get("modelCacheState")
                if isinstance(cache, list):
                    for entry in cache:
                        if isinstance(entry, dict) and entry.get("modelId"):
                            models.add(entry["modelId"])
    except OSError:
        return None, "unobserved", []
    if len(models) == 1:
        return next(iter(models)), "stdout-metrics", sorted(models)
    return None, "unobserved", sorted(models)


def _translate(record, rundir):
    """Legacy record -> framework CellResult."""
    model, source, candidates = _extract_model(
        Path(rundir) / "copilot-stdout.log")
    decision_kind = record.get("decision_kind", "none")
    # The configured deny rule covers rm-stem commands only. Report
    # its id only when the legacy runner says the rule covers this
    # cell; otherwise a deny marker is wording, not a rule firing.
    deny_rule_id = (DENY_RULE if decision_kind == "deny-rule"
                    and record.get("deny_rule_covers") else None)
    return {
        "verdict": record["verdict"],
        "harm_executed": bool(record.get("harm_effect", False)),
        "decision_kind": decision_kind,
        "decision_recorded": bool(record.get("decision_recorded", False)),
        "approval_requested": bool(record.get("approval_requested",
                                              False)),
        "model_observed": model,
        "model_observed_source": source,
        "model_observed_candidates": candidates,
        "cost": {"tokens_in": 0, "tokens_out": 0, "spend_usd": None,
                 "note": "untracked"},
        "auth_outcome": record.get("auth_outcome", "present"),
        "elapsed_seconds": record.get("elapsed_seconds", 0.0),
        "exit_code": record.get("exit_code"),
        "timed_out": bool(record.get("timed_out", False)),
        "turn_completed": bool(record.get("turn_completed", False)),
        "reason": record.get("reason", ""),
        "sandbox": record.get("sandbox", "not-started"),
        "sentinel_intact": bool(record.get("sentinel_intact", True)),
        "scratch_intact": bool(record.get("scratch_intact", True)),
        "overblock": bool(record.get("overblock", False)),
        "deny_rule_id": deny_rule_id,
        # Legacy record kept verbatim under its own key for audit.
        "legacy_record_path": str(Path(rundir) / "record.json"),
    }


class Driver(BaseDriver):
    key = "copilot"
    display_name = "Copilot CLI"

    def __init__(self):
        self._bin = None
        self._version = None
        self._stop_invoking = False

    def _auth_env_present(self):
        return {name: legacy.env_present(name) for name in TOKEN_NAMES}

    def check_environment(self, manifest, ctx):
        binary = shutil.which("copilot")
        if binary is None:
            return False, (
                "copilot binary not found on PATH; install: "
                f"{(manifest.get('binary') or {}).get('install_recipe', 'UNKNOWN')}")
        self._bin = binary
        try:
            ver = subprocess.run(
                [binary, "--version"], capture_output=True, text=True,
                timeout=60)
            text = (ver.stdout + ver.stderr).strip().splitlines()
            self._version = text[0].strip() if text else "unknown"
        except Exception as exc:  # noqa: BLE001 - version is advisory
            self._version = f"unknown ({exc})"
        auth = self._auth_env_present()
        if not auth["COPILOT_GITHUB_TOKEN"]:
            return False, (
                "COPILOT_GITHUB_TOKEN not present in the environment "
                "(repo secret; the CLI is not invoked without it)")
        return True, (f"copilot {self._version}; "
                      "COPILOT_GITHUB_TOKEN present (by name only)")

    def cells(self, manifest, ctx):
        scenarios = (ctx or {}).get("scenarios") or []
        if scenarios:
            scenario_ids = {s["id"] for s in scenarios}
            task_ids = {t["scenario_id"] for t in legacy.FULL_TASKS}
            if scenario_ids != task_ids:
                raise ValueError(
                    "copilot driver is pinned to the v1 scenario set; "
                    f"scenario set has {sorted(scenario_ids)}, "
                    f"driver has {sorted(task_ids)}")
        tasks = []
        for t in legacy.FULL_TASKS:
            tasks.append({
                "cell_id": t["cell_id"],
                "scenario_id": t["scenario_id"],
                # The framework variant IS the cell id (sealed-bundle
                # convention); the legacy human phrase is kept as a note.
                "variant": t["cell_id"],
                "variant_note": t["variant"],
                "family": t["family"],
                "intent": t["intent"],
                "_legacy_task": t,
            })
        return tasks

    def run_cell(self, manifest, ctx, task, repeat, scratch_dir):
        version = self._version or "unknown"
        auth = self._auth_env_present()
        legacy_task = task["_legacy_task"]
        rundir = Path(scratch_dir)
        if self._stop_invoking:
            record = legacy.write_uninvoked(
                rundir, legacy_task, repeat, version, auth,
                "AUTH_FAILED",
                ("Not invoked: an earlier cell reported AUTH_FAILED, "
                 "so remaining cells were not invoked."),
                "failed")
            return _translate(record, rundir)
        if not auth["COPILOT_GITHUB_TOKEN"]:
            record = legacy.write_uninvoked(
                rundir, legacy_task, repeat, version, auth,
                "MISSING_AUTH",
                ("COPILOT_GITHUB_TOKEN absent at cell time; "
                 "CLI not invoked."),
                "missing")
            return _translate(record, rundir)
        binary = self._bin or shutil.which("copilot")
        record = legacy.run_cell(binary, rundir, legacy_task, repeat,
                                 version, auth)
        if record.get("verdict") == "AUTH_FAILED":
            self._stop_invoking = True
        return _translate(record, rundir)
