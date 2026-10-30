#!/usr/bin/env python3
"""Reproducible end-to-end Nemotron demo (the video is built from this).

  invariant -> Nemotron proposal (Token Factory, live) ->
  Decision verdict (deterministic checker, pinned oracle) ->
  Effect in containment (throwaway sandbox only)

Safety contract (non-negotiable, printed by every run):
  - A proposed argv is NEVER executed merely because it was proposed.
  - Forbidden / prompt / unknown verdicts are NEVER executed: their
    Effect observation is "not executed; sentinel intact".
  - The ONLY executed command is an allow-verdict benign command that
    passes the safety gate (binary in {ls, cat, head, git, echo} and
    every path argument under the throwaway sandbox), or — if no
    proposal qualifies — the labelled positive control `ls <sandbox>`.
  - The Decision check itself (codex execpolicy check) executes nothing;
    it only asks the native checker what it would decide.

Proposal transport (two modes, same endpoint and model):
  --tf-helper PATH (default: the registered connector helper, when it
    exists): the helper swaps a surrogate for the real credential only
    on an approved request to the registered host. No key enters this
    repo, this script, or the evidence file.
  --direct: the repo module's own client with NEBIUS_API_KEY from the
    environment (for users running this with their own Token Factory key).
  --proposal-json FILE: re-use a live proposal already obtained (model,
    content, usage, request/response timestamps) verbatim instead of
    proposing twice — e.g. when the first caller's timeout was too short
    for a reasoning model and a longer-timeout caller on the same
    endpoint re-ran it. The file's own timestamps are kept in evidence.

Usage:
  python3 tools/run_nemotron_demo.py \\
      --invariants FP-001,FP-002,FP-003 \\
      --model nvidia/nemotron-3-super-120b-a12b \\
      --policy fixtures/policies/default.rules \\
      --out evidence/nebius-2026-10-30/

Writes <out>/demo-evidence.json and prints the demo transcript.
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import nemotron_scenarios as NS  # noqa: E402

DEFAULT_TF_HELPER = Path.home() / "workspace" / "custom-connectors" / \
    "custom.nebius" / "bin" / "tf.py"
BENIGN_BINARIES = {"ls", "cat", "head", "git", "echo"}
SAFETY_CONTRACT = (
    "SAFETY: proposed commands are checked, never executed, except one "
    "allow-verdict benign command passing the safety gate inside a "
    "throwaway sandbox. Forbidden/prompt/unknown proposals are never run."
)


def propose_via_helper(helper, model, prompt, max_tokens):
    proc = subprocess.run(
        [sys.executable, str(helper), "chat", "--model", model,
         "--prompt", prompt, "--max-tokens", str(max_tokens)],
        capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"tf helper failed: {proc.stderr.strip()[-500:]}")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"tf helper output is not JSON: {e}") from e
    content = out.get("content") or ""
    if not content.strip():
        raise RuntimeError("tf helper returned empty content")
    return {"model": out.get("model", model), "content": content,
            "usage": out.get("usage", {})}


def safety_gate(argv, sandbox):
    """True only for a benign, sandbox-contained command."""
    if not argv or argv[0] not in BENIGN_BINARIES:
        return False
    sb = str(sandbox)
    for tok in argv[1:]:
        if tok.startswith("-"):
            if tok in ("-rf", "-fr", "--recursive", "--force", "-r", "-f"):
                return False
            continue
        if tok.startswith("/") and not tok.startswith(sb + "/") and tok != sb:
            return False
        if ".." in Path(tok).parts:
            return False
    return True


def run_effect(verdicts, sandbox):
    """Live Effect observation in a throwaway sandbox (see module docstring)."""
    sandbox.mkdir(parents=True, exist_ok=True)
    sentinel = sandbox / "sentinel.txt"
    sentinel.write_text("fineprint-demo-sentinel: do-not-delete\n")
    before = hashlib.sha256(sentinel.read_bytes()).hexdigest()

    executed = None
    for v in verdicts:
        if v["actual_decision"] == "allow" and safety_gate(v["argv"], sandbox):
            proc = subprocess.run(v["argv"], capture_output=True, text=True,
                                  cwd=str(sandbox), timeout=60)
            executed = {"scenario_id": v["scenario_id"], "argv": v["argv"],
                        "returncode": proc.returncode,
                        "stdout": proc.stdout.strip()[:500],
                        "stderr": proc.stderr.strip()[:500]}
            break
    if executed is None:
        proc = subprocess.run(["ls", str(sandbox)], capture_output=True,
                              text=True, cwd=str(sandbox), timeout=60)
        executed = {"scenario_id": "POSITIVE-CONTROL (not a proposal)",
                    "argv": ["ls", str(sandbox)],
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.strip()[:500],
                    "stderr": proc.stderr.strip()[:500]}

    after = hashlib.sha256(sentinel.read_bytes()).hexdigest()
    per_scenario = []
    for v in verdicts:
        if v["scenario_id"] == (executed.get("scenario_id")):
            effect = "executed (allow-verdict benign command, sandbox only)"
        elif v["actual_decision"] in ("forbidden", "prompt"):
            effect = "not_executed (Decision forbids/prompts; never run)"
        elif v["actual_decision"] == "unknown":
            effect = ("not_executed (unknown = no Decision; Approval and "
                      "sandbox still govern; never run as a bypass test)")
        else:
            effect = "not_executed"
        per_scenario.append({"scenario_id": v["scenario_id"],
                             "actual_decision": v["actual_decision"],
                             "effect": effect})
    return {
        "sandbox": str(sandbox),
        "sentinel_before_sha256": before,
        "sentinel_after_sha256": after,
        "sentinel_intact": before == after,
        "executed_command": executed,
        "per_scenario_effect": per_scenario,
        "safety_contract": SAFETY_CONTRACT,
    }


def parse_args(argv):
    a = {"invariants": ["FP-001", "FP-002", "FP-003"],
         "model": NS.DEFAULT_MODEL,
         "policy": "fixtures/policies/default.rules", "out": None,
         "variants_per_invariant": 2, "max_tokens": 8192,
         "temperature": 0.7, "harness": "codex",
         "tf_helper": None, "direct": False, "proposal_json": None}
    i = 0
    while i < len(argv):
        t = argv[i]
        if t == "--invariants":
            a["invariants"] = [x.strip() for x in argv[i + 1].split(",") if x.strip()]; i += 2
        elif t == "--model":
            a["model"] = argv[i + 1]; i += 2
        elif t == "--policy":
            a["policy"] = argv[i + 1]; i += 2
        elif t == "--out":
            a["out"] = argv[i + 1]; i += 2
        elif t == "--variants-per-invariant":
            a["variants_per_invariant"] = int(argv[i + 1]); i += 2
        elif t == "--max-tokens":
            a["max_tokens"] = int(argv[i + 1]); i += 2
        elif t == "--temperature":
            a["temperature"] = float(argv[i + 1]); i += 2
        elif t == "--harness":
            a["harness"] = argv[i + 1]; i += 2
        elif t == "--tf-helper":
            a["tf_helper"] = argv[i + 1]; i += 2
        elif t == "--direct":
            a["direct"] = True; i += 1
        elif t == "--proposal-json":
            a["proposal_json"] = argv[i + 1]; i += 2
        elif t in ("-h", "--help"):
            print(__doc__); sys.exit(0)
        else:
            sys.exit(f"unknown flag: {t}\n{__doc__}")
    return a


def main(argv):
    args = parse_args(argv)
    print(SAFETY_CONTRACT)
    invariants = NS.load_invariants(args["invariants"])
    prompt = NS.build_prompt(invariants, args["variants_per_invariant"])
    started = NS.utcnow()
    if args["proposal_json"]:
        # A live proposal already obtained (e.g. via a longer-timeout
        # caller using the same registered endpoint and credential):
        # re-use it verbatim instead of proposing twice. The file holds
        # model, content, usage, and its own request/response timestamps.
        raw = json.loads(Path(args["proposal_json"]).read_text())
        if not (raw.get("content") or "").strip():
            sys.exit("--proposal-json has empty content")
        started = raw.get("requested_at", started)
        transport = "live Token Factory call (proposal file, same endpoint)"
        proposed_at = raw.get("responded_at", NS.utcnow())
    elif args["direct"]:
        # Direct mode: the caller's own key from the environment. This
        # branch and the helper branch never mix in one run.
        import os as _os
        raw = NS.call_token_factory(args["model"], prompt,
                                    _os.environ.get("NEBIUS_API_KEY"),
                                    max_tokens=args["max_tokens"],
                                    temperature=args["temperature"])
        transport = "direct (NEBIUS_API_KEY env)"
    else:
        helper = Path(args["tf_helper"]) if args["tf_helper"] else DEFAULT_TF_HELPER
        if not helper.exists():
            sys.exit(f"--tf-helper not found: {helper} (pass --direct with "
                     "NEBIUS_API_KEY, or --tf-helper PATH)")
        raw = propose_via_helper(helper, args["model"], prompt,
                                 args["max_tokens"])
        transport = f"connector helper ({helper})"
    if not args["proposal_json"]:
        # Live-call branches: proposal landed just now. The proposal-file
        # branch keeps its own response timestamp (set above).
        proposed_at = NS.utcnow()
    valid_ids = {i["id"] for i in invariants}
    scenarios = NS.parse_scenarios(raw["content"], valid_ids)
    verdicts = NS.check_scenarios(scenarios, args["policy"],
                                  harness=args["harness"])
    sandbox = Path(tempfile.mkdtemp(prefix="fineprint-nemotron-demo-"))
    effect = run_effect(verdicts, sandbox)
    evidence = {
        "demo": "invariant -> Nemotron proposal -> Decision verdict -> "
                "Effect in containment",
        "transport": transport,
        "provider": "Nebius Token Factory",
        "endpoint_host": "api.tokenfactory.nebius.com",
        "model_requested": args["model"],
        "model_returned": raw["model"],
        "started_at": started,
        "proposed_at": proposed_at,
        "checked_at": NS.utcnow(),
        "usage": raw["usage"],
        "invariants": invariants,
        "prompt": prompt,
        "raw_model_response": raw["content"],
        "scenarios": scenarios,
        "decision_verdicts": verdicts,
        "effect": effect,
        "counts": {
            "proposed": len(scenarios),
            "checked": len(verdicts),
            "matches_expected": sum(1 for v in verdicts
                                    if v["decision_matches_expected"]),
        },
    }
    if args["out"]:
        out = Path(args["out"])
        out.mkdir(parents=True, exist_ok=True)
        (out / "demo-evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n")
        print(f"wrote {out}/demo-evidence.json")
    print(f"\nmodel: {evidence['model_returned']} via {transport}")
    for s, v in zip(scenarios, verdicts):
        print(f"\nINVARIANT {s['invariant_id']}: {s['title']}")
        print(f"  proposal: {' '.join(s['argv'])}")
        print(f"  rationale: {s['rationale']}")
        print(f"  Decision: {v['actual_decision']} "
              f"(model predicted {s['expected_decision']})")
    print(f"\nEffect: sandbox {sandbox}, sentinel intact: "
          f"{effect['sentinel_intact']}")
    print(f"  executed (only benign allow/control): "
          f"{' '.join(effect['executed_command']['argv'])} "
          f"-> rc={effect['executed_command']['returncode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
