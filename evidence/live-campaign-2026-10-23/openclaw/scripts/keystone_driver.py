#!/usr/bin/env python3
"""Keystone approval driver for OpenClaw live measurement (FinePrint Stage 4).

Drives agent turns through the running Gateway, polls `openclaw approvals
pending --json`, records every pending approval record verbatim (A4), and
resolves it with the case's pre-declared decision (A3 witness). Sentinel
state is checked at pending-time and after the turn (E1).

No credentials in this file: all openclaw calls go through oc_cli.py, which
mints the surrogate in-memory and passes it via process env only.
"""
import json, os, subprocess, sys, time
from datetime import datetime, timezone

SB_ROOT = os.path.expanduser("~/workspace/agent-boundary-conformance-live-sandbox-openclaw")
WS = SB_ROOT + "/workspace"
STAGE = SB_ROOT + "/evidence-staging"
CLI = ["python3", STAGE + "/scripts/oc_cli.py"]

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def oc(args, timeout=60):
    r = subprocess.run(CLI + args, capture_output=True, text=True, timeout=timeout)
    return r

def pending():
    r = oc(["approvals", "pending", "--json"], timeout=45)
    try:
        return json.loads(r.stdout).get("approvals", []), r.stdout.strip()
    except Exception:
        return [], "PARSE_FAIL: " + (r.stdout or "")[:300] + " ERR: " + (r.stderr or "")[:300]

def resolve(appr_id, decision):
    r = oc(["approvals", "resolve", appr_id, decision, "--json"], timeout=45)
    return {"id": appr_id, "decision": decision, "exit": r.returncode,
            "stdout": (r.stdout or "")[:800], "stderr": (r.stderr or "")[:400]}

def run_case(case_id, session, command, decision, sentinel):
    """decision: deny|allow-once|allow-always|NONE (no prompt expected).
    sentinel: path whose existence is the effect signal."""
    rec = {"case_id": case_id, "session": session, "command": command,
           "declared_decision": decision, "sentinel": sentinel,
           "started_at": now(), "pending_records": [], "resolutions": [],
           "sentinel_exists_at_pending": None, "agent_exit": None}
    msg = "Use the exec tool to run exactly this shell command and nothing else: " + command
    out_path = f"{STAGE}/agent-{case_id}.json"
    with open(out_path, "w") as out, open(f"{STAGE}/agent-{case_id}.err", "w") as err:
        proc = subprocess.Popen(CLI + ["agent", "--agent", "main", "--session-id", session,
                                       "--message", msg, "--json"],
                                stdout=out, stderr=err)
        deadline = time.time() + 420
        seen_ids = set()
        while proc.poll() is None and time.time() < deadline:
            apps, _raw = pending()
            for a in apps:
                aid = a.get("id") or a.get("requestId") or json.dumps(a)[:40]
                if aid in seen_ids:
                    continue
                seen_ids.add(aid)
                if rec["sentinel_exists_at_pending"] is None and sentinel:
                    rec["sentinel_exists_at_pending"] = os.path.exists(sentinel)
                rec["pending_records"].append({"captured_at": now(), "record": a})
                print(f"[{case_id}] PENDING {aid} -> resolving {decision}", flush=True)
                if decision != "NONE":
                    rec["resolutions"].append(resolve(aid, decision))
            time.sleep(2)
        try:
            rec["agent_exit"] = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill(); rec["agent_exit"] = "TIMEOUT-KILLED"
    rec["finished_at"] = now()
    if sentinel:
        rec["sentinel_exists_after"] = os.path.exists(sentinel)
    try:
        rec["agent_result"] = json.load(open(out_path))
    except Exception as e:
        rec["agent_result"] = {"parse_error": str(e)}
    return rec

def main():
    cases = json.load(open(sys.argv[1]))
    results = []
    for c in cases:
        print(f"=== {c['case_id']}: {c['command']} (decision={c['decision']}) ===", flush=True)
        r = run_case(c["case_id"], c["session"], c["command"], c["decision"], c.get("sentinel"))
        results.append(r)
        print(f"    pending={len(r['pending_records'])} resolutions={len(r['resolutions'])} "
              f"sentinel_at_pending={r['sentinel_exists_at_pending']} sentinel_after={r.get('sentinel_exists_after')} "
              f"agent_exit={r['agent_exit']}", flush=True)
        if c.get("between"):
            p = c["between"]  # driver-side reset of the sentinel between phases
            if os.path.exists(p):
                os.remove(p)
                print(f"    driver reset: removed {p}", flush=True)
    json.dump(results, open(sys.argv[2], "w"), indent=2)
    print("driver done:", sys.argv[2])

if __name__ == "__main__":
    main()
