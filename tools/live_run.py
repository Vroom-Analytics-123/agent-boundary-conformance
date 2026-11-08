#!/usr/bin/env python3
"""Live runner framework — one CLI for live harness measurement.

Simplicity bar (Anish, Nov 7): the free tier must be usable by the
most junior dev, or even a non-dev working with a harness —
point-and-click or one simple instruction, one command, zero config
for a first verdict. So the first verdict is one command that names
only the harness; everything else (repeats, scenario set, output
dir, proxy, sealing) comes from the repo-shipped manifest and
defaults. No config file to write, no flags to learn first:

    python3 tools/live_run.py copilot-cli

The explicit forms below do the same thing and exist for scripts
and operators who want to say more.

    python3 tools/live_run.py run copilot-cli --repeats 2 --sign
    python3 tools/live_run.py list-harnesses
    python3 tools/live_run.py status --harness copilot-cli
    python3 tools/live_run.py verify --bundle <bundle.json>
    python3 tools/live_run.py compare --baseline <sealed.json> \
        --fresh <new.json>

One CLI, per-harness driver plugins (tools/live_drivers/), one record
schema (schemas/live_run_record.v1.schema.json), proxy lifecycle
(tools/live_proxy.py), cost logging, and Merkle sealing in one
command. The sealed Nov 4 bundles are regression oracles: `compare`
normalizes both the sealed live-bundle.v1 shape and the new
live-run-record.v1 shape into (variant, repeat) -> verdict and
reports regressions.

Design notes (from docs/live-runs-audit-2026-11-07.md):
  - Repeats default to 2 (the Nov 4 live standard: 24 variants x 2).
  - Records are per VARIANT with repeats[] inside (the sealed bundles
    are per (variant, repeat) rows; compare normalizes both).
  - The bundle tally for a variant is its WORST repeat (harm in any
    repeat marks the cell "executed"); harm_total counts cells with
    harm in any repeat. The per-cell record's top-level verdict is
    repeat 1 (primary), matching the sealed bundles' per-cell shape.
  - The runner never overwrites an existing output dir: pick a new
    --out. Sealed bundles and existing records are never modified.
  - Fail closed: a missing binary, missing auth, or an unready proxy
    produces MISSING_AUTH / not_run records, never a guessed PASS.
  - Secrets are named only, never read or logged.
"""

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import attribution as AT  # noqa: E402
import live_drivers.base as LB  # noqa: E402
import live_proxy as LP  # noqa: E402
import live_yaml as LY  # noqa: E402
import schemas_v1 as S1  # noqa: E402

SCHEMA_VERSION = "live-run-record.v1"
SEALED_SCHEMA_VERSION = "live-bundle.v1"

VERDICTS = ("PASS", "FAIL_HARM", "FAIL_NO_DECISION", "FAIL_TIMEOUT",
            "MISSING_AUTH", "AUTH_FAILED")
# Worst-repeat ordering for bundle tallies: harm beats no-decision
# beats pass beats not-run.
_TALLY_SEVERITY = {"executed": 3, "no_decision": 2, "pass": 1,
                   "not_run": 0}
_MANIFEST_STATUSES = ("live", "blocked", "not_applicable")


def _utc_compact():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path):
    return S1.sha256_file(str(path))


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def _positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"not an integer: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(
            f"repeats must be >= 1, got {value}")
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="live_run",
        description="Live runner framework for harness measurement.",
        epilog="First verdict, one command: "
               "python3 tools/live_run.py <harness> (e.g. copilot-cli) "
               "— no config file, no flags. "
               "python3 tools/live_run.py list-harnesses shows the "
               "harnesses you can name.")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run one harness's live cells")
    r.add_argument("harness_pos", nargs="?", default=None,
                   help="harness key, e.g. copilot-cli "
                        "(same as --harness)")
    r.add_argument("--harness", default=None,
                   help="harness key, e.g. copilot-cli")
    r.add_argument("--repeats", type=_positive_int, default=2,
                   help="repeats per variant (default 2, Nov 4 standard)")
    r.add_argument("--out", default=None,
                   help="output dir (default "
                        "framework/scorecard/<harness>-pilot-v1)")
    r.add_argument("--label", default=None,
                   help="run label (default: harness key)")
    r.add_argument("--scenario-set", default=None,
                   help="scenario JSON (default: the manifest's)")
    r.add_argument("--seal", action="store_true",
                   help="seal the bundle (default: sealing is "
                        "unconditional; this states intent)")
    r.add_argument("--sign", action="store_true",
                   help="also sign with the repo Ed25519 key "
                        "(fails loudly when no key exists)")

    sub.add_parser("list-harnesses", help="list manifests and drivers")

    s = sub.add_parser("status", help="readiness gate for one harness")
    s.add_argument("--harness", required=True)

    v = sub.add_parser("verify", help="verify a live bundle")
    v.add_argument("--bundle", required=True)

    c = sub.add_parser("compare",
                       help="diff a fresh bundle against a sealed "
                            "baseline (regression oracle)")
    c.add_argument("--baseline", required=True)
    c.add_argument("--fresh", required=True)
    c.add_argument("--out", default=None,
                   help="write the diff JSON here")
    return parser


_SUBCOMMANDS = ("run", "list-harnesses", "status", "compare", "verify")


def parse_args(argv=None):
    # argv=None means "read sys.argv" — normalize it to a list first,
    # or the bare-harness rewrite below never sees the real CLI args.
    if argv is None:
        argv = sys.argv[1:]
    # Simplicity bar: a bare KNOWN harness name is a run with all
    # defaults (python3 tools/live_run.py copilot-cli). Anything
    # starting with "-" is left alone so --help and flags keep
    # working, and an unknown word stays an unknown subcommand
    # (argparse errors) instead of silently becoming a bad harness.
    if (argv is not None and argv and argv[0] not in _SUBCOMMANDS
            and not argv[0].startswith("-")
            and (REPO / "adapters" / f"{argv[0]}.live.yaml").exists()):
        argv = ["run", argv[0], *argv[1:]]
    args = vars(build_parser().parse_args(argv))
    if args["command"] == "run":
        harness = args.get("harness") or args.pop("harness_pos", None)
        if not harness:
            build_parser().error(
                "run requires a harness: "
                "python3 tools/live_run.py <harness> (e.g. copilot-cli)")
        args["harness"] = harness
    return args


# ---------------------------------------------------------------------------
# Manifests and scenarios
# ---------------------------------------------------------------------------

def load_manifest(key, manifests_dir=None):
    """Load adapters/<key>.live.yaml. Raises ValueError when the
    manifest is missing or malformed."""
    d = Path(manifests_dir) if manifests_dir else REPO / "adapters"
    path = d / f"{key}.live.yaml"
    if not path.exists():
        raise ValueError(f"no live manifest for harness {key!r}: "
                         f"{path} does not exist")
    manifest = LY.parse_yaml(path.read_text())
    if manifest.get("harness") != key:
        raise ValueError(
            f"manifest {path} says harness "
            f"{manifest.get('harness')!r}, expected {key!r}")
    if manifest.get("status") not in _MANIFEST_STATUSES:
        raise ValueError(
            f"manifest {path}: unknown status "
            f"{manifest.get('status')!r}")
    manifest["_path"] = str(path.relative_to(REPO))
    return manifest


def load_scenarios(path):
    """Load and validate a scenarios JSON file (24 entries, v1)."""
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        raise ValueError(f"cannot read scenarios {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError(f"scenarios {path}: expected a non-empty list")
    seen = set()
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError(f"scenarios {path}: entry is not an object")
        for field in ("id", "argv", "family", "intent"):
            if field not in entry:
                raise ValueError(
                    f"scenarios {path}: entry missing {field!r}: {entry}")
        if entry["id"] in seen:
            raise ValueError(
                f"scenarios {path}: duplicate scenario id "
                f"{entry['id']!r}")
        seen.add(entry["id"])
        if entry["intent"] not in AT.LIVE_INTENTS:
            raise ValueError(
                f"scenarios {path}: scenario {entry['id']} has unknown "
                f"intent {entry['intent']!r}")
        if not isinstance(entry["argv"], list) or not entry["argv"]:
            raise ValueError(
                f"scenarios {path}: scenario {entry['id']} has no argv")
    return data


# ---------------------------------------------------------------------------
# Records, tallies, sealing, verification
# ---------------------------------------------------------------------------

def tally_from_verdict(verdict):
    """Map a cell verdict to its tally group (sealed-bundle vocabulary)."""
    if verdict == "FAIL_HARM":
        return "executed"
    if verdict == "PASS":
        return "pass"
    if verdict in ("FAIL_NO_DECISION", "FAIL_TIMEOUT"):
        return "no_decision"
    if verdict in ("MISSING_AUTH", "AUTH_FAILED"):
        return "not_run"
    raise ValueError(f"unknown verdict: {verdict!r}")


def _sum_cost(per_repeat):
    tokens_in = tokens_out = 0
    spend = 0.0
    spend_known = True
    untracked = False
    for rep in per_repeat:
        cost = rep.get("cost") or {}
        tokens_in += cost.get("tokens_in") or 0
        tokens_out += cost.get("tokens_out") or 0
        if cost.get("spend_usd") is None:
            spend_known = False
        else:
            spend += cost["spend_usd"]
        if cost.get("note") == "untracked":
            untracked = True
    return {"tokens_in": tokens_in, "tokens_out": tokens_out,
            "spend_usd": round(spend, 6) if spend_known else None,
            "note": "untracked" if untracked else ""}


def build_cell_record(cell_meta, per_repeat, deny_rule_id=None):
    """Assemble one per-variant record from its repeat results.

    cell_meta: cell_id, scenario_id, variant, family, intent, driver,
    driver_version. per_repeat: list of repeat dicts (repeat, verdict,
    decision_kind, harm_executed, model_observed,
    model_observed_source, ...). The deny rule id comes from each
    repeat's own deny_rule_id when present, else the argument.
    """
    if not per_repeat:
        raise ValueError("build_cell_record needs at least one repeat")
    repeats = sorted(per_repeat, key=lambda r: r["repeat"])
    if [r["repeat"] for r in repeats] != list(range(1, len(repeats) + 1)):
        raise ValueError("repeats must be numbered 1..n consecutively")
    intent = cell_meta["intent"]
    built = []
    for rep in repeats:
        if rep["verdict"] not in VERDICTS:
            raise ValueError(f"unknown verdict: {rep['verdict']!r}")
        if rep["decision_kind"] not in AT.LIVE_DECISION_KINDS:
            raise ValueError(
                f"unknown decision_kind: {rep['decision_kind']!r}")
        rec = dict(rep)
        attr = AT.attribute_live_cell(
            intent=intent, decision_kind=rep["decision_kind"],
            harm_executed=bool(rep["harm_executed"]),
            deny_rule_id=rep.get("deny_rule_id", deny_rule_id))
        rec["non_attempt_attribution"] = (
            attr["non_attempt_attribution"] if attr else None)
        rec["attribution_rule_id"] = (
            attr["attribution_rule_id"] if attr else None)
        built.append(rec)
    primary = built[0]
    summary = AT.summarize_live_repeats(
        [r["decision_kind"] for r in built])
    # The record's "agreement" is VERDICT agreement — the
    # regression-relevant question (did the repeats agree on the
    # outcome?). The decision-kind distribution is in outcomes /
    # modal_decision. A cell can agree on the decision and still split
    # on the verdict (e.g. deny-rule both times, harm once).
    summary["agreement"] = (
        "unanimous" if len({r["verdict"] for r in built}) == 1
        else "split")
    summary["verdicts"] = {}
    for rep in built:
        summary["verdicts"][rep["verdict"]] = (
            summary["verdicts"].get(rep["verdict"], 0) + 1)
    record = {
        "cell_id": cell_meta["cell_id"],
        "scenario_id": cell_meta["scenario_id"],
        "variant": cell_meta["variant"],
        "family": cell_meta["family"],
        "intent": intent,
        "driver": cell_meta["driver"],
        "driver_version": cell_meta["driver_version"],
        "verdict": primary["verdict"],
        "tally": tally_from_verdict(primary["verdict"]),
        "model_observed": primary.get("model_observed"),
        "model_observed_source": primary.get("model_observed_source"),
        "cost": _sum_cost(built),
        "repeats": built,
        "repeat_summary": summary,
    }
    return record


def compute_tallies(records):
    """Bundle tallies from per-variant records.

    by_group counts each variant once, by its WORST repeat tally;
    harm_total counts variants with harm in any repeat; verdict_counts
    counts every repeat's verdict.
    """
    by_group = {}
    total = {"executed": 0, "pass": 0, "no_decision": 0, "not_run": 0}
    verdict_counts = {}
    harm_total = 0
    for rec in records:
        worst = max(
            (tally_from_verdict(r["verdict"]) for r in rec["repeats"]),
            key=lambda t: _TALLY_SEVERITY[t])
        group = by_group.setdefault(rec["variant"], {})
        group[worst] = group.get(worst, 0) + 1
        total[worst] += 1
        if worst == "executed":
            harm_total += 1
        for rep in rec["repeats"]:
            verdict_counts[rep["verdict"]] = (
                verdict_counts.get(rep["verdict"], 0) + 1)
    return {"by_group": by_group, "total": total,
            "verdict_counts": verdict_counts,
            "harm_total": harm_total}, harm_total


def seal_live_bundle(*, label, harness, harness_version, model, records,
                     run_meta, driver, manifest, caveats=None, files=None):
    """Build a sealed live bundle dict from per-variant records.

    Merkle: leaves are leaf_hash_for_finding(cell) over the exact cell
    dicts stored in the bundle (schemas_v1.build_merkle). The bundle
    is self-describing: driver + manifest provenance, run_meta, and
    the tallies are all re-derivable by verify_live_bundle.
    """
    records = copy.deepcopy(records)
    for rec in records:
        rec.setdefault("source_path", f"records/{rec['cell_id']}.json")
    leaves = [S1.leaf_hash_for_finding(rec) for rec in records]
    root, _proofs = S1.build_merkle(leaves)
    tallies, harm_total = compute_tallies(records)
    created = _utc_compact()
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": f"live-{harness}-{label}-{created}",
        "label": label,
        "harness": harness,
        "harness_version": harness_version,
        "model": model,
        "route": "live",
        "grouping": ["variant"],
        "created_utc": created,
        "status": "valid",
        "signature_state": "unsigned",
        "witness_state": "unwitnessed",
        "signature": None,
        "approvals": None,
        "cell_count": len(records),
        "harm_total": harm_total,
        "tallies": tallies,
        "merkle": {
            "leaf_algorithm": "sha256(0x00 || canonical_json(cell))",
            "node_algorithm": "sha256(0x01 || left || right)",
            "root": root,
            "leaves": [{"cell_id": rec["cell_id"], "leaf": leaf}
                       for rec, leaf in zip(records, leaves)],
        },
        "cells": records,
        "driver": driver,
        "manifest": manifest,
        "run_meta": run_meta,
        "caveats": list(caveats or []),
        "files": list(files or []),
        "exclusions": [],
        "cell_note": ("Per-variant records with repeats[] inside; "
                      "top-level verdict is repeat 1 (primary). "
                      "Bundle tally per variant is the worst repeat."),
    }


_CELL_REQUIRED = ("cell_id", "scenario_id", "variant", "family", "intent",
                  "driver", "driver_version", "verdict", "tally",
                  "repeats", "repeat_summary", "source_path",
                  "model_observed", "model_observed_source")
_REPEAT_REQUIRED = ("repeat", "verdict", "decision_kind", "harm_executed",
                    "model_observed", "model_observed_source",
                    "non_attempt_attribution", "attribution_rule_id")


def verify_live_bundle(bundle):
    """Re-derive everything checkable in a live bundle.

    Returns a list of problem strings (empty = verified). Checks:
    schema version, status, cell/repeat shape, primary-verdict and
    tally consistency, tallies + harm_total + cell_count, and the
    Merkle root over the stored cells.
    """
    problems = []
    if not isinstance(bundle, dict):
        return ["bundle is not an object"]
    if bundle.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"schema_version is {bundle.get('schema_version')!r}, "
            f"expected {SCHEMA_VERSION!r}")
    if bundle.get("status") != "valid":
        problems.append(f"status is {bundle.get('status')!r}, "
                        "expected 'valid'")
    cells = bundle.get("cells")
    if not isinstance(cells, list) or not cells:
        problems.append("cells is empty or missing")
        return problems
    for rec in cells:
        for field in _CELL_REQUIRED:
            if field not in rec:
                problems.append(
                    f"{rec.get('cell_id', '?')}: missing {field}")
        if rec.get("verdict") not in VERDICTS:
            problems.append(
                f"{rec.get('cell_id', '?')}: unknown verdict "
                f"{rec.get('verdict')!r}")
            continue
        try:
            if rec.get("tally") != tally_from_verdict(rec["verdict"]):
                problems.append(
                    f"{rec['cell_id']}: tally {rec.get('tally')!r} "
                    f"does not match verdict {rec['verdict']!r}")
        except ValueError:
            pass
        repeats = rec.get("repeats")
        if not isinstance(repeats, list) or not repeats:
            problems.append(f"{rec.get('cell_id', '?')}: no repeats")
            continue
        if [r.get("repeat") for r in repeats] != list(
                range(1, len(repeats) + 1)):
            problems.append(
                f"{rec['cell_id']}: repeats are not numbered 1..n")
        if repeats[0].get("verdict") != rec.get("verdict"):
            problems.append(
                f"{rec['cell_id']}: top-level verdict "
                f"{rec.get('verdict')!r} != repeat 1 verdict "
                f"{repeats[0].get('verdict')!r}")
        for rep in repeats:
            for field in _REPEAT_REQUIRED:
                if field not in rep:
                    problems.append(
                        f"{rec['cell_id']}/r{rep.get('repeat', '?')}: "
                        f"missing {field}")
            if rep.get("decision_kind") not in AT.LIVE_DECISION_KINDS:
                problems.append(
                    f"{rec['cell_id']}/r{rep.get('repeat', '?')}: "
                    f"unknown decision_kind {rep.get('decision_kind')!r}")
            if rep.get("non_attempt_attribution") not in (
                    None, *AT.ATTRIBUTIONS):
                problems.append(
                    f"{rec['cell_id']}/r{rep.get('repeat', '?')}: "
                    "unknown non_attempt_attribution "
                    f"{rep.get('non_attempt_attribution')!r}")
    if bundle.get("cell_count") != len(cells):
        problems.append(
            f"cell_count is {bundle.get('cell_count')}, "
            f"but there are {len(cells)} cells")
    try:
        tallies, harm_total = compute_tallies(cells)
        if bundle.get("tallies") != tallies:
            problems.append(
                "tally mismatch: stored tallies do not re-derive "
                "from cells")
        if bundle.get("harm_total") != harm_total:
            problems.append(
                f"harm_total is {bundle.get('harm_total')}, "
                f"re-derived {harm_total}")
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        problems.append(f"tally re-derivation failed: {exc}")
    merkle = bundle.get("merkle") or {}
    try:
        leaves = [S1.leaf_hash_for_finding(rec) for rec in cells]
        root, _ = S1.build_merkle(leaves)
        if merkle.get("root") != root:
            problems.append("merkle root does not re-derive from cells")
        stored = [l.get("cell_id") for l in merkle.get("leaves", [])]
        if stored != [rec["cell_id"] for rec in cells]:
            problems.append("merkle leaves do not match cells in order")
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        problems.append(f"merkle re-derivation failed: {exc}")
    return problems


# ---------------------------------------------------------------------------
# Compare (regression oracle)
# ---------------------------------------------------------------------------

def normalize_live_bundle_v1(bundle):
    """Normalize either bundle shape to {(variant, repeat): verdict}.

    Sealed live-bundle.v1: cells are per (variant, repeat) rows with
    repeat "r1"/"r2". New live-run-record.v1: cells are per-variant
    records with repeats[] inside.
    """
    version = bundle.get("schema_version")
    out = {}
    if version == SEALED_SCHEMA_VERSION:
        for cell in bundle.get("cells", []):
            repeat = int(str(cell["repeat"]).lstrip("r"))
            out[(cell["variant"], repeat)] = cell["verdict"]
    elif version == SCHEMA_VERSION:
        for rec in bundle.get("cells", []):
            for rep in rec.get("repeats", []):
                out[(rec["variant"], rep["repeat"])] = rep["verdict"]
    else:
        raise ValueError(
            f"cannot normalize bundle with schema_version "
            f"{version!r}")
    return out


def _is_regression(baseline_verdict, fresh_verdict):
    if fresh_verdict == "FAIL_HARM" and baseline_verdict != "FAIL_HARM":
        return True
    if baseline_verdict == "PASS" and fresh_verdict in (
            "FAIL_NO_DECISION", "FAIL_TIMEOUT"):
        return True
    return False


def _is_improvement(baseline_verdict, fresh_verdict):
    if fresh_verdict == "PASS" and baseline_verdict != "PASS":
        return True
    if (baseline_verdict == "FAIL_HARM"
            and fresh_verdict == "FAIL_NO_DECISION"):
        return True
    return False


def compare_bundles(baseline, fresh):
    """Diff a fresh bundle against a sealed baseline.

    Returns {"baseline_cells", "fresh_cells", "decision_flips",
    "regressions", "improvements", "regression_count", "missing",
    "added"}. A flip is {"cell": "V1-01-direct/r1", "baseline": ...,
    "fresh": ...}. Regressions are harm newly executed or a decision
    newly lost; improvements are harm stopped or a decision newly
    recorded.
    """
    base = normalize_live_bundle_v1(baseline)
    new = normalize_live_bundle_v1(fresh)
    flips, regressions, improvements = [], [], []
    for key in sorted(set(base) | set(new)):
        variant, repeat = key
        label = f"{variant}/r{repeat}"
        if key not in base or key not in new:
            continue
        if base[key] == new[key]:
            continue
        flip = {"cell": label, "baseline": base[key], "fresh": new[key]}
        flips.append(flip)
        if _is_regression(base[key], new[key]):
            regressions.append(flip)
        elif _is_improvement(base[key], new[key]):
            improvements.append(flip)
    missing = [f"{v}/r{r}" for (v, r) in sorted(set(base) - set(new))]
    added = [f"{v}/r{r}" for (v, r) in sorted(set(new) - set(base))]
    return {"baseline_cells": len(base), "fresh_cells": len(new),
            "decision_flips": flips, "regressions": regressions,
            "improvements": improvements,
            "regression_count": len(regressions),
            "missing": missing, "added": added}


# ---------------------------------------------------------------------------
# Status gate
# ---------------------------------------------------------------------------

def _surrogate_importable():
    import importlib.util
    return importlib.util.find_spec(
        "dynamic_credentials",
        ["/opt/muse/skills/custom-connector-setup/bin"]) is not None


def status_harness(key, manifests_dir=None):
    """Readiness gate for one harness. Returns (ok, gaps).

    Checks only what can be established without values: binary on
    PATH, secret NAME present in the environment (repo secrets are
    passed as env vars on Actions), driver implemented, proxy script
    present, workflow present, scenario set present. A subscription
    login can never be verified non-interactively — it is always a
    gap with that reason stated.
    """
    manifest = load_manifest(key, manifests_dir=manifests_dir)
    gaps = []
    binary = manifest.get("binary") or {}
    name = binary.get("name")
    if name and shutil.which(name) is None:
        gaps.append(
            f"binary {name!r} not found on PATH "
            f"(install: {binary.get('install_recipe', 'UNKNOWN')})")
    auth = manifest.get("auth") or {}
    method = auth.get("method")
    if method == "repo-secret":
        secret = auth.get("secret_name")
        if secret and os.environ.get(secret) is None:
            gaps.append(
                f"secret {secret} not present in the environment "
                "(repo secret; set it to run)")
    elif method == "subscription-login":
        gaps.append(
            f"login required: {auth.get('account', 'UNKNOWN')} "
            "(interactive login; cannot verify here)")
    elif method == "dummy+proxy":
        if not _surrogate_importable():
            gaps.append(
                "dummy+proxy auth needs dynamic_credentials, which is "
                "not importable on this machine")
    elif method == "none":
        pass
    else:
        gaps.append(f"auth method {method!r} is not established")
    driver_key = manifest.get("driver")
    if driver_key is None:
        gaps.append("no driver implemented yet (next harness)")
    else:
        try:
            LB.load_driver(driver_key)
        except LB.DriverError as exc:
            gaps.append(f"driver {driver_key!r}: {exc}")
    proxy = manifest.get("proxy")
    if proxy:
        script = proxy.get("script")
        if script and not (REPO / script).exists():
            gaps.append(f"proxy script missing: {script}")
        if proxy.get("port") in (None, 0):
            gaps.append("proxy spec has no port")
    workflow = manifest.get("workflow")
    if workflow and workflow != "UNKNOWN" and not (REPO / workflow).exists():
        gaps.append(f"workflow missing: {workflow}")
    scenario_set = manifest.get("scenario_set")
    if scenario_set and not (REPO / scenario_set).exists():
        gaps.append(f"scenario set missing: {scenario_set}")
    return (not gaps), gaps


def list_harnesses(manifests_dir=None):
    """All manifests with their readiness summary."""
    d = Path(manifests_dir) if manifests_dir else REPO / "adapters"
    rows = []
    for path in sorted(d.glob("*.live.yaml")):
        m = LY.parse_yaml(path.read_text())
        rows.append({
            "harness": m.get("harness"),
            "status": m.get("status"),
            "driver": m.get("driver"),
            "binary_pin": (m.get("binary") or {}).get("version_pin"),
            "auth_method": (m.get("auth") or {}).get("method"),
        })
    return rows


# ---------------------------------------------------------------------------
# The run loop
# ---------------------------------------------------------------------------

def _driver_plugin_sha256(driver):
    module = sys.modules.get(type(driver).__module__)
    path = getattr(module, "__file__", None)
    if path and Path(path).exists():
        return _sha256_file(Path(path))
    return "0" * 64


def _missing_auth_result(task, repeat, reason, sandbox):
    return {
        "repeat": repeat, "verdict": "MISSING_AUTH",
        "harm_executed": False, "decision_kind": "none",
        "decision_recorded": False, "approval_requested": False,
        "model_observed": None, "model_observed_source": "unobserved",
        "cost": {"tokens_in": 0, "tokens_out": 0, "spend_usd": None,
                 "note": "untracked"},
        "auth_outcome": "missing", "elapsed_seconds": 0.0,
        "exit_code": None, "timed_out": False, "turn_completed": False,
        "reason": reason, "sandbox": sandbox, "sentinel_intact": True,
        "scratch_intact": True, "overblock": False,
        "deny_rule_id": None}


def run_harness(*, driver, manifest, repeats, out_dir, label,
                scenario_set_path=None, sign=False):
    """Run one harness's cells and seal the bundle.

    Never overwrites an existing output dir. Returns the sealed
    bundle dict. If the environment check fails, every cell is
    recorded as MISSING_AUTH (fail closed) and the bundle is still
    sealed — a missing-auth run is evidence, not a crash.
    """
    out_dir = Path(out_dir)
    if (out_dir / "bundle.json").exists():
        raise FileExistsError(
            f"{out_dir}/bundle.json already exists — refusing to "
            "overwrite existing records; pick a new --out")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "records").mkdir(exist_ok=True)
    (out_dir / "scratch").mkdir(exist_ok=True)

    started = _utc_iso()
    scenario_path = (Path(scenario_set_path) if scenario_set_path
                     else REPO / manifest.get(
                         "scenario_set",
                         "framework/scorecard/scenarios-v1.json"))
    scenarios = load_scenarios(scenario_path)
    ctx = {"repo_root": REPO, "scenarios": scenarios,
           "repeats": repeats, "manifest": manifest}
    sandbox_mode = (manifest.get("sandbox") or {}).get("mode",
                                                       "not-started")

    ok, reason = driver.check_environment(manifest, ctx)
    tasks = driver.cells(manifest, ctx)

    proxy_proc = None
    proxy_info = None
    proxy_spec = manifest.get("proxy")
    if proxy_spec and ok:
        spec = LP.ProxySpec(
            script=str(REPO / proxy_spec["script"]),
            port=proxy_spec["port"],
            args=tuple(proxy_spec.get("args", [])),
            health_path=proxy_spec.get("health_path"),
            log_path=str(out_dir / "proxy.log"))
        proxy_proc = LP.start_proxy(spec, timeout=60.0)
        proxy_info = {"script": proxy_spec["script"],
                      "port": proxy_spec["port"],
                      "health_path": proxy_spec.get("health_path")}

    records = []
    try:
        for task in tasks:
            per_repeat = []
            for repeat in range(1, repeats + 1):
                if not ok:
                    result = _missing_auth_result(
                        task, repeat, reason, sandbox_mode)
                else:
                    scratch = (out_dir / "scratch" / task["cell_id"]
                               / f"r{repeat}")
                    scratch.mkdir(parents=True, exist_ok=True)
                    result = driver.run_cell(
                        manifest, ctx, task, repeat, scratch)
                    result = dict(result)
                    result["repeat"] = repeat
                per_repeat.append(result)
            record = build_cell_record(
                {"cell_id": task["cell_id"],
                 "scenario_id": task["scenario_id"],
                 "variant": task["variant"],
                 "family": task["family"],
                 "intent": task["intent"],
                 "driver": driver.key,
                 "driver_version": manifest.get("binary", {}).get(
                     "version_pin", "UNKNOWN")},
                per_repeat)
            record["source_path"] = f"records/{task['cell_id']}.json"
            (out_dir / "records" / f"{task['cell_id']}.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n")
            records.append(record)
    finally:
        if proxy_proc is not None:
            LP.stop_proxy(proxy_proc)

    model = next(
        (r["model_observed"] for r in records
         if r.get("model_observed")), None)
    model_str = model or "unpinned, not recorded"
    manifest_path = manifest.get("_path") or (
        f"adapters/{manifest.get('harness')}.live.yaml")
    manifest_sha = (_sha256_file(REPO / manifest_path)
                    if (REPO / manifest_path).exists() else "0" * 64)
    run_meta = {
        "repeats": repeats,
        "scenario_set": {"path": str(scenario_path.relative_to(REPO))
                         if scenario_path.is_relative_to(REPO)
                         else str(scenario_path),
                         "sha256": _sha256_file(scenario_path)},
        "sandbox": sandbox_mode,
        "proxy": proxy_info,
        "cost": _sum_cost([rep for rec in records
                           for rep in rec["repeats"]]),
        "started_at": started,
        "finished_at": _utc_iso(),
        "check_environment": {"ok": ok, "reason": reason},
    }
    bundle = seal_live_bundle(
        label=label, harness=manifest.get("harness"),
        harness_version=manifest.get("binary", {}).get(
            "version_pin", "UNKNOWN"),
        model=model_str, records=records, run_meta=run_meta,
        driver={"name": driver.key,
                "version": manifest.get("binary", {}).get(
                    "version_pin", "UNKNOWN"),
                "plugin_sha256": _driver_plugin_sha256(driver)},
        manifest={"path": manifest_path, "sha256": manifest_sha})
    bundle_path = out_dir / "bundle.json"
    bundle_path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    problems = verify_live_bundle(bundle)
    if problems:
        raise RuntimeError(
            f"sealed bundle failed verification: {problems}")
    if sign:
        import bundle_signing
        bundle_signing.sign_new_bundle(bundle, bundle_path)
        bundle_path.write_text(
            json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    return bundle


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    args = parse_args(argv)
    command = args["command"]
    if command == "list-harnesses":
        for row in list_harnesses():
            print(f"{row['harness']:<14} {row['status']:<15} "
                  f"driver={row['driver'] or '-':<10} "
                  f"pin={row['binary_pin']} auth={row['auth_method']}")
        return 0
    if command == "status":
        ok, gaps = status_harness(args["harness"])
        print(f"{args['harness']}: {'READY' if ok else 'NOT READY'}")
        for gap in gaps:
            print(f"  - {gap}")
        return 0 if ok else 2
    if command == "verify":
        bundle = json.loads(Path(args["bundle"]).read_text())
        problems = verify_live_bundle(bundle)
        if not problems:
            print(f"{args['bundle']}: VERIFIED "
                  f"({bundle.get('cell_count')} cells, merkle "
                  f"{bundle.get('merkle', {}).get('root', '')[:12]}...)")
            return 0
        print(f"{args['bundle']}: {len(problems)} problem(s)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    if command == "compare":
        baseline = json.loads(Path(args["baseline"]).read_text())
        fresh = json.loads(Path(args["fresh"]).read_text())
        diff = compare_bundles(baseline, fresh)
        print(f"baseline {diff['baseline_cells']} cells, "
              f"fresh {diff['fresh_cells']} cells; "
              f"{len(diff['decision_flips'])} flip(s), "
              f"{diff['regression_count']} regression(s), "
              f"{len(diff['improvements'])} improvement(s)")
        for flip in diff["decision_flips"]:
            print(f"  {flip['cell']}: {flip['baseline']} -> "
                  f"{flip['fresh']}")
        if diff["missing"]:
            print(f"  missing in fresh: {', '.join(diff['missing'])}")
        if diff["added"]:
            print(f"  added in fresh: {', '.join(diff['added'])}")
        if args.get("out"):
            Path(args["out"]).write_text(
                json.dumps(diff, indent=2, sort_keys=True) + "\n")
        return 0 if diff["regression_count"] == 0 else 1
    if command == "run":
        try:
            manifest = load_manifest(args["harness"])
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print("try: python3 tools/live_run.py list-harnesses",
                  file=sys.stderr)
            return 2
        driver_key = manifest.get("driver")
        if driver_key is None:
            print(f"harness {args['harness']!r} has no driver yet "
                  "(next harness); refusing to guess one",
                  file=sys.stderr)
            return 2
        try:
            driver = LB.load_driver(driver_key)
        except LB.DriverError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        out_dir = (Path(args["out"]) if args["out"]
                   else REPO / "framework" / "scorecard"
                   / f"{args['harness']}-pilot-v1")
        label = args["label"] or args["harness"]
        bundle = run_harness(
            driver=driver, manifest=manifest,
            repeats=args["repeats"], out_dir=out_dir, label=label,
            scenario_set_path=args.get("scenario_set"),
            sign=args["sign"])
        print(f"bundle: {out_dir}/bundle.json")
        print(f"cells: {bundle['cell_count']}  "
              f"harm_total: {bundle['harm_total']}  "
              f"tallies: {bundle['tallies']['total']}")
        print(f"merkle: {bundle['merkle']['root']}")
        print(f"model: {bundle['model']}")
        return 0
    raise AssertionError(f"unknown command {command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
