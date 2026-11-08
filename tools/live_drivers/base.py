#!/usr/bin/env python3
"""Driver plugin interface for the live runner.

A driver wraps ONE harness's own invocation (binary, session driver,
or proxy) and turns it into per-cell results the framework can
record, tally, and seal. The framework owns everything else: CLI,
manifests, proxy lifecycle, repeats, attribution, cost logging,
sealing, and comparison.

Driver contract (all three methods must be implemented):
  - check_environment(manifest, ctx) -> (ok: bool, reason: str)
      Fail closed: return (False, reason) when the binary is missing,
      the auth is absent, or the harness cannot run here. The reason
      names the missing thing only — never a secret value.
  - cells(manifest, ctx) -> list[dict]
      One task dict per variant to run. Each task carries at least:
      cell_id, scenario_id, variant, family, intent. The scenario
      list arrives in ctx["scenarios"].
  - run_cell(manifest, ctx, task, repeat, scratch_dir) -> dict
      One repeat of one cell. Returns a CellResult dict with:
        verdict: PASS | FAIL_HARM | FAIL_NO_DECISION | FAIL_TIMEOUT
                 | MISSING_AUTH | AUTH_FAILED
        harm_executed: bool — the measured effect happened
        decision_kind: deny-rule | model-refusal | none
        decision_recorded: bool — the harness recorded a decision
        approval_requested: bool
        model_observed: str | None — the model actually observed
        model_observed_source: stdout-metrics | session | unobserved
        cost: {tokens_in, tokens_out, spend_usd, note}
        auth_outcome: present | missing | failed
        elapsed_seconds, exit_code, timed_out, turn_completed: bool
        reason: str
        sandbox: str (mode from the manifest)
        sentinel_intact, scratch_intact, overblock: bool
        deny_rule_id: str | None — the rule the harness cited, if any
      Extra keys are preserved into the record verbatim.
"""

import importlib
import sys
from pathlib import Path


class DriverError(Exception):
    """Raised when a driver cannot be loaded or does not implement the
    interface. Never raised for a harness run failing — that is a
    per-cell result, not a framework error."""


class BaseDriver:
    key = None            # registry key, e.g. "copilot"
    display_name = None   # human name, e.g. "Copilot CLI"
    # Version measured from the live binary by check_environment
    # (e.g. "2026.11.05-86047df"). None when the driver does not
    # measure one. live_run.py prefers this over the manifest's
    # version_pin, which is "UNKNOWN" for a floating install (F5).

    def check_environment(self, manifest, ctx):
        raise NotImplementedError

    def cells(self, manifest, ctx):
        raise NotImplementedError

    def run_cell(self, manifest, ctx, task, repeat, scratch_dir):
        raise NotImplementedError


def _validate(driver, key):
    if not isinstance(driver, BaseDriver):
        raise DriverError(
            f"driver {key!r}: Driver is not a BaseDriver")
    for method in ("check_environment", "cells", "run_cell"):
        if getattr(type(driver), method) is getattr(BaseDriver, method):
            raise DriverError(
                f"driver {key!r}: Driver does not implement "
                f"{method}()")
    if driver.key not in (None, key):
        raise DriverError(
            f"driver {key!r}: Driver.key is {driver.key!r}")


def load_driver(key, drivers_dir=None, _module=None):
    """Load and instantiate the driver for `key`.

    drivers_dir overrides the package directory (tests point it at a
    temp dir). _module injects an already-imported module (tests only).
    Raises DriverError for unknown keys, missing modules, and drivers
    that do not implement the interface.
    """
    if _module is not None:
        module = _module
    else:
        if drivers_dir is not None:
            sys.path.insert(0, str(drivers_dir))
        try:
            module = importlib.import_module(f"live_drivers.{key}")
        except ModuleNotFoundError:
            raise DriverError(
                f"no driver for harness {key!r}: "
                f"live_drivers/{key}.py is not implemented yet")
        except Exception as exc:  # noqa: BLE001 - re-wrap as DriverError
            raise DriverError(
                f"driver {key!r} failed to import: {exc}") from exc
    cls = getattr(module, "Driver", None)
    if cls is None:
        # Fall back to the first BaseDriver subclass defined in it.
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type)
                    and issubclass(obj, BaseDriver)
                    and obj is not BaseDriver):
                cls = obj
                break
    if cls is None:
        raise DriverError(
            f"driver {key!r}: module defines no Driver class")
    driver = cls()
    _validate(driver, key)
    return driver


def implemented_drivers():
    """Keys of the drivers present in this package."""
    pkg = Path(__file__).resolve().parent
    out = []
    for path in sorted(pkg.glob("*.py")):
        if path.name in ("__init__.py", "base.py"):
            continue
        out.append(path.stem)
    return out
