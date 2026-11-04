#!/usr/bin/env python3
"""MSP approver client (human gate), CI VARIANT for the public-repo smoke
probe. Derived from the local approver at
competitions/meta-hackathon/stretch-musecode/unblock/approver.py
(private program repo). Policy: v1 deny-all per APPROVER-POLICY.md
(see the branch README for the policy summary; the policy of record
lives in the program repo).

CI ADAPTATIONS (every change vs the local file, documented here):
1. NO vault/surrogate path. The local file mints a credential surrogate
   via dynamic_credentials (a container-side mechanism that does not
   exist on a GitHub runner). This variant reads the key ONLY from the
   environment variable named by --key-from-env (the workflow passes
   the MUSE_HEADLESS_KEY Actions secret as env). There is no fallback:
   provider=meta without --key-from-env raises before spawning.
2. --muse-bin flag. The local file hardcodes the workspace install
   path; CI installs fresh via the audited launcher and passes the
   installed path. The local path remains the default so the file
   still runs locally with an env key.
3. Literal-key scrub. The local file scrubs surrogate patterns from
   written logs; this variant instead replaces the literal env key
   value (when >= 8 chars) in every written log file, defense in
   depth. The key is never printed, never passed as an argument,
   never echoed: environment only.
4. No dynamic_credentials import, no sys.path hack for it.

Everything else — MSP wire protocol, reader/dispatcher thread split
(the deadlock fix), v1 choice selection order, user-input decline,
retry (max 3), turn/cancel on undecidable — is UNCHANGED from local.

Usage (CI):
  approver.py --rundir DIR --prompt "..." --policy v1
      --provider meta --model muse-spark-1.3 --approval-mode onRequest
      --turn-timeout 600 --muse-bin /path/to/muse
      --key-from-env MUSE_HEADLESS_KEY
"""
import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

MUSE_BIN_DEFAULT = Path.home() / ("workspace/agent-boundary-program/competitions/"
    "meta-hackathon/stretch-musecode/install/muse")

_KEY_VALUE = None


def redact(text):
    if _KEY_VALUE and len(_KEY_VALUE) >= 8:
        text = text.replace(_KEY_VALUE, "[REDACTED-KEY]")
    return text


def uuid7():
    ms = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0xFFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFFFFFFFFFFFFFF
    val = (ms << 80) | (7 << 76) | (rand_a << 64) | (0x8000000000000000 | rand_b)
    h = "%032x" % val
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])


class Approver:
    def __init__(self, args):
        self.args = args
        self.rundir = Path(args.rundir).resolve()
        self.outdir = Path(args.out).resolve() if args.out else self.rundir
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.msg_log = open(self.outdir / "msp-messages.jsonl", "w")
        self.err_log = open(self.outdir / "serve-stderr.log", "w")
        self.next_id = 1
        self.pending = {}  # jsonrpc id -> {"event": threading.Event, "result": ..., "error": ...}
        self.pending_lock = threading.Lock()
        self.dispatch_queue = queue.Queue()
        self.decided = set()  # (approvalId, sourceIndex) already decided
        self.attempts = {}  # (approvalId, sourceIndex) -> failed decide attempts
        self.decisions = []
        self.turn_done = threading.Event()
        self.turn_status = None
        self.turn_id = None
        self.session_id = None
        self.errors = []
        self.stop_reader = False
        self.proc = None

    def log_msg(self, direction, obj):
        try:
            self.msg_log.write(json.dumps({"dir": direction, "msg": obj},
                                          default=str) + "\n")
            self.msg_log.flush()
        except Exception:  # noqa: BLE001
            pass

    def send(self, obj):
        line = json.dumps(obj)
        self.proc.stdin.write((line + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        self.log_msg("out", obj)

    def request(self, method, params, timeout=120):
        rid = self.next_id
        self.next_id += 1
        ev = threading.Event()
        with self.pending_lock:
            self.pending[rid] = {"event": ev, "result": None, "error": None}
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        if not ev.wait(timeout):
            with self.pending_lock:
                self.pending.pop(rid, None)
            raise TimeoutError("no response to %s within %ss" % (method, timeout))
        with self.pending_lock:
            slot = self.pending.pop(rid)
        if slot["error"] is not None:
            raise RuntimeError("request %s failed: %s" % (method, slot["error"]))
        return slot["result"]

    def notify(self, method, params):
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    # ---- inbound dispatch ----
    # Reader thread ONLY reads + routes responses to slots + enqueues
    # notifications. A separate dispatcher thread handles notifications,
    # because handling may send blocking requests (approval/decide) whose
    # responses only the reader can deliver. Handling in the reader thread
    # deadlocks: proven by proof run 1 (decide sent, response arrived, but
    # unread until the 120s handler timeout).
    def route(self, obj):
        self.log_msg("in", obj)
        if "id" in obj and ("result" in obj or "error" in obj):
            with self.pending_lock:
                slot = self.pending.get(obj["id"])
            if slot is not None:
                slot["result"] = obj.get("result")
                slot["error"] = obj.get("error")
                slot["event"].set()
            return
        self.dispatch_queue.put(obj)

    def dispatcher_loop(self):
        while not self.stop_reader:
            try:
                obj = self.dispatch_queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                self.handle(obj)
            except Exception as e:  # noqa: BLE001
                self.errors.append("dispatcher: %r" % (e,))

    def handle(self, obj):
        method = obj.get("method", "")
        params = obj.get("params", {}) or {}
        try:
            if method in ("approval/requested", "approval/updated"):
                self.maybe_decide(params)
            elif method == "approval/resolved":
                pass  # terminal recorded in decisions via resolved stream; kept in messages log
            elif method == "turn/completed":
                self.turn_status = (params.get("status")
                                    or params.get("terminal")
                                    or params.get("outcome"))
                self.turn_id = params.get("turnId") or self.turn_id
                self.turn_done.set()
            elif method == "turn/started":
                self.turn_id = params.get("turnId") or self.turn_id
            elif method == "userInput/requested":
                self.decline_user_input(params)
        except Exception as e:  # noqa: BLE001
            self.errors.append("handler %s: %r" % (method, e))

    def decline_user_input(self, params):
        # v1: tasks need no user input; a prompt left open would hang the run.
        uid = params.get("userInputId") or params.get("promptId") or params.get("id")
        if not uid or not self.session_id:
            self.errors.append("userInput/requested without id/session; skipped")
            return
        try:
            self.request("userInput/cancel", {
                "commandId": uuid7(), "sessionId": self.session_id,
                "userInputId": uid,
                "reason": "approver v1: no user input in measurement runs"},
                timeout=60)
        except Exception as e:  # noqa: BLE001
            self.errors.append("userInput/cancel failed: %r" % (e,))

    def pick_deny(self, choices):
        """v1 selection order. Returns (choice, kind) or (None, 'undecidable')."""
        by_dec = {}
        for c in choices or []:
            by_dec.setdefault(c.get("decision"), []).append(c)
        for c in by_dec.get("denied", []):
            if c.get("scope") == "once":
                return c, "deny-once"
        if by_dec.get("denied"):
            return by_dec["denied"][0], "deny"
        if by_dec.get("abort"):
            return by_dec["abort"][0], "abort"
        return None, "undecidable"

    def maybe_decide(self, params):
        approval_id = params.get("approvalId")
        req = params.get("currentRequirementId") or {}
        key = (approval_id, req.get("sourceIndex"))
        if approval_id is None or key in self.decided:
            return
        if self.args.policy != "v1":
            raise RuntimeError("unknown policy %s" % self.args.policy)
        choice, kind = self.pick_deny(params.get("availableChoices"))
        rec = {"approvalId": approval_id, "sourceIndex": req.get("sourceIndex"),
               "toolName": params.get("toolName"),
               "subject": params.get("subject"),
               "rawArgs": str(params.get("rawArgs", ""))[:500],
               "judgeEscalated": params.get("judgeEscalated"),
               "reviewerReason": params.get("reviewerReason"),
               "protectedWrite": params.get("protectedWrite"),
               "offered": [{"choiceId": c.get("choiceId"), "decision": c.get("decision"),
                            "label": c.get("label"), "scope": c.get("scope")}
                           for c in (params.get("availableChoices") or [])],
               "picked": None, "kind": kind, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        if choice is None:
            rec["error"] = "no deny/abort choice offered"
            self.decisions.append(rec)
            self.decided.add(key)
            # End the turn rather than leave an undecidable approval pending.
            try:
                self.request("turn/cancel", {"commandId": uuid7(),
                                             "sessionId": self.session_id},
                             timeout=60)
            except Exception as e:  # noqa: BLE001
                self.errors.append("turn/cancel after undecidable failed: %r" % (e,))
            return
        try:
            self.request("approval/decide", {
                "approvalId": approval_id, "choiceId": choice["choiceId"],
                "commandId": uuid7(), "requirementId": req,
                "sessionId": self.session_id}, timeout=120)
        except Exception as e:  # noqa: BLE001
            # Record the attempt (the approval must not become invisible)
            # but do NOT mark decided: the next poll/updated re-tries, up
            # to 3 failed attempts, after which the requirement is marked
            # decide-failed and left pending (classified by outcome).
            self.attempts[key] = self.attempts.get(key, 0) + 1
            rec["error"] = "decide failed: %r" % (e,)
            rec["attempt"] = self.attempts[key]
            rec["kind"] = "decide-failed" if self.attempts[key] >= 3 else "decide-retry"
            self.decisions.append(rec)
            if self.attempts[key] >= 3:
                self.decided.add(key)
            return
        rec["picked"] = {"choiceId": choice["choiceId"],
                         "decision": choice.get("decision"),
                         "label": choice.get("label"),
                         "scope": choice.get("scope")}
        self.decisions.append(rec)
        self.decided.add(key)

    def poll_pending(self):
        try:
            res = self.request("approval/listPending",
                               {"sessionId": self.session_id}, timeout=60)
        except Exception as e:  # noqa: BLE001
            self.errors.append("listPending failed: %r" % (e,))
            return
        for appr in (res or {}).get("approvals", []):
            try:
                self.maybe_decide(appr)
            except Exception as e:  # noqa: BLE001
                self.errors.append("poll decide failed: %r" % (e,))

    # ---- process plumbing ----
    def reader_loop(self):
        buf = b""
        stream = self.proc.stdout
        try:
            while not self.stop_reader:
                chunk = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    if buf.startswith(b"Content-Length:"):
                        head, sep, rest = buf.partition(b"\r\n\r\n")
                        if not sep:
                            break
                        ln = None
                        for part in head.split(b"\r\n"):
                            if part.lower().startswith(b"content-length:"):
                                ln = int(part.split(b":", 1)[1].strip())
                        if ln is None or len(rest) < ln:
                            break
                        raw, buf = rest[:ln], rest[ln:]
                        self.dispatch(raw)
                    else:
                        line, sep, rest = buf.partition(b"\n")
                        if not sep:
                            break
                        buf = rest
                        line = line.strip()
                        if line:
                            self.dispatch(line)
        except Exception as e:  # noqa: BLE001
            self.errors.append("reader loop: %r" % (e,))
        finally:
            self.turn_done.set()

    def dispatch(self, raw):
        try:
            text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
            obj = json.loads(text)
        except Exception as e:  # noqa: BLE001
            self.errors.append("bad message %r: %r" % (raw[:200], e))
            return
        # The key is never persisted: it travels in env only, and every
        # written log is scrubbed of its literal value at the end.
        self.route(obj)

    def stderr_loop(self):
        try:
            for raw in self.proc.stderr:
                line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
                self.err_log.write(redact(line))
                self.err_log.flush()
        except Exception:  # noqa: BLE001
            pass

    def run(self):
        global _KEY_VALUE
        env = dict(os.environ)
        if self.args.provider == "meta":
            if not self.args.key_from_env:
                raise RuntimeError(
                    "CI approver requires --key-from-env (vault minting does "
                    "not exist on a runner); refusing to spawn without a key")
            key = os.environ.get(self.args.key_from_env)
            if not key:
                raise RuntimeError("env %s is unset or empty" % self.args.key_from_env)
            _KEY_VALUE = key
            env["META_API_KEY"] = key
            env["MODEL_API_KEY"] = key
        cmd = [str(self.args.muse_bin), "serve", "--provider", self.args.provider]
        if self.args.provider == "meta":
            cmd += ["--model", self.args.model]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     cwd=str(self.rundir), env=env,
                                     text=False, bufsize=0)
        rt = threading.Thread(target=self.reader_loop, daemon=True)
        dt = threading.Thread(target=self.dispatcher_loop, daemon=True)
        et = threading.Thread(target=self.stderr_loop, daemon=True)
        rt.start()
        dt.start()
        et.start()
        summary = {"provider": self.args.provider, "policy": self.args.policy,
                   "model_requested": self.args.model if self.args.provider == "meta" else None,
                   "approval_mode": self.args.approval_mode, "rundir": str(self.rundir)}
        try:
            init = self.request("initialize", {
                "clientInfo": {"name": "fineprint_approver", "version": "1.0"}},
                timeout=120)
            summary["initialize"] = init
            self.notify("initialized", {})
            start_params = {"commandId": uuid7(),
                            "approvalMode": self.args.approval_mode,
                            "workspaceRoots": [str(self.rundir)]}
            if self.args.provider == "meta":
                start_params["modelId"] = self.args.model
            started = self.request("session/start", start_params, timeout=180)
            sess = (started or {}).get("session", {}) or {}
            self.session_id = sess.get("sessionId")
            summary["session"] = sess
            if not self.session_id:
                raise RuntimeError("session/start returned no sessionId: %s" % (started,))
            t0 = time.time()
            self.request("turn/start", {
                "commandId": uuid7(), "sessionId": self.session_id,
                "input": [{"type": "text", "text": self.args.prompt}]},
                timeout=120)
            deadline = t0 + self.args.turn_timeout
            last_poll = 0
            while not self.turn_done.wait(timeout=5):
                now = time.time()
                if now > deadline:
                    summary["timeout"] = True
                    try:
                        self.request("turn/cancel",
                                     {"commandId": uuid7(), "sessionId": self.session_id},
                                     timeout=60)
                    except Exception as e:  # noqa: BLE001
                        self.errors.append("turn/cancel on timeout failed: %r" % (e,))
                    self.turn_done.wait(timeout=60)
                    break
                if now - last_poll >= 10:
                    last_poll = now
                    self.poll_pending()
            summary["turn_status"] = self.turn_status
            summary["turn_seconds"] = round(time.time() - t0, 1)
            summary["decisions"] = len(self.decisions)
        except Exception as e:  # noqa: BLE001
            summary["fatal"] = repr(e)
            self.errors.append("run fatal: %r" % (e,))
        finally:
            self.stop_reader = True
            try:
                self.proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=20)
            try:
                self.msg_log.close()
                self.err_log.close()
            except Exception:  # noqa: BLE001
                pass
        # Scrub the written logs (defense in depth; the key travels in env
        # only and should never appear, but a child echoing env would be
        # caught here).
        for fn in ("msp-messages.jsonl", "serve-stderr.log"):
            p = self.outdir / fn
            if p.exists():
                txt = p.read_text(errors="replace")
                if _KEY_VALUE and _KEY_VALUE in txt:
                    p.write_text(redact(txt))
        (self.outdir / "msp-decisions.json").write_text(
            json.dumps(self.decisions, indent=2, default=str))
        summary["errors"] = self.errors
        (self.outdir / "approver-summary.json").write_text(
            json.dumps(summary, indent=2, default=str))
        print(json.dumps(summary, default=str))
        return 0 if (self.turn_status and not summary.get("timeout")
                     and "fatal" not in summary) else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--policy", default="v1")
    ap.add_argument("--provider", default="meta")
    ap.add_argument("--model", default="muse-spark-1.3")
    ap.add_argument("--approval-mode", default="onRequest")
    ap.add_argument("--turn-timeout", type=int, default=600)
    ap.add_argument("--out", default=None)
    ap.add_argument("--muse-bin", default=str(MUSE_BIN_DEFAULT))
    ap.add_argument("--key-from-env", default=None)
    a = ap.parse_args()
    return Approver(a).run()


if __name__ == "__main__":
    sys.exit(main())

