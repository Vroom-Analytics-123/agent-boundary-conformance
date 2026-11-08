#!/usr/bin/env python3
"""Proxy lifecycle for the live runner, plus the generic OpenAI-
compatible proxy server the framework ships for model-agnostic
harness drivers.

Lifecycle (used by tools/live_run.py):
  start_proxy(spec) -> Popen   — start, wait for the health check,
                                  raise ProxyError on timeout
  stop_proxy(proc)             — terminate, kill if stubborn
  tcp_health(port) / http_health(url)

The per-harness proxies that predate the framework live in
tools/proxies/ (vendored verbatim from ~/workspace with provenance
headers). This module's generic server is the repo-native proxy for
new drivers: it forwards /v1/chat/completions to one arm, rewriting
ONLY the `model` field to the arm model, exactly like
framework/scorecard/live-agents-v1/runners/proxy.py (which it
supersedes for framework runs — the live-agents copy is left
untouched as the Nov 3 record).

  python3 tools/live_proxy.py serve --port 8891 --arm cheaper \
      --model beam-free
  python3 tools/live_proxy.py serve --port 8892 --arm meta \
      --model muse-spark-1.1

Auth uses the dynamic-credential surrogate helper exactly as the
connector CLIs do: no raw key ever appears in chat, files, logs, or
agent environments. The surrogate import is lazy (inside serve) so
`import live_proxy` works on any checkout.
"""

import argparse
import dataclasses
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ARMS = {
    "cheaper": ("https://api.cheaperinference.com/v1",
                "custom.cheaperinference",
                ["api.cheaperinference.com"]),
    "meta": ("https://api.meta.ai/v1",
             "custom.meta-model-api",
             ["api.meta.ai"]),
}


class ProxyError(Exception):
    """A proxy could not be started, failed its health check, or could
    not be stopped."""


@dataclasses.dataclass
class ProxySpec:
    """How to start one proxy process.

    script: repo-relative path to a proxy script (run with the current
            Python); or command: an explicit argv list. Exactly one.
    port: the TCP port the proxy must listen on.
    args: extra argv for a script.
    health_path: HTTP path to GET for readiness (None = TCP connect
                 only — the Claude proxy has no HTTP health endpoint).
    cwd: working directory for the process.
    log_path: file to append the proxy's stdout/stderr to.
    """
    script: str | None = None
    command: list | None = None
    port: int = 0
    args: tuple = ()
    health_path: str | None = None
    cwd: str | None = None
    log_path: str | None = None

    def argv(self):
        if self.command is not None:
            return list(self.command)
        if self.script is not None:
            return [sys.executable, self.script, *self.args]
        raise ProxyError("ProxySpec needs a script or a command")


def tcp_health(port, timeout=2.0):
    try:
        with socket.create_connection(("127.0.0.1", port),
                                      timeout=timeout):
            return True
    except OSError:
        return False


def http_health(url, timeout=2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _healthy(spec, timeout=2.0):
    if not tcp_health(spec.port, timeout=timeout):
        return False
    if spec.health_path:
        return http_health(
            f"http://127.0.0.1:{spec.port}{spec.health_path}",
            timeout=timeout)
    return True


def start_proxy(spec, timeout=30.0):
    """Start the proxy and wait until it answers its health check.

    Raises ProxyError on timeout or on early exit. The process is
    started in its own session so stop_proxy can kill the whole group.
    """
    argv = spec.argv()
    log = None
    if spec.log_path:
        log = open(spec.log_path, "ab")  # noqa: SIM115 - closed by caller
    try:
        proc = subprocess.Popen(
            argv, cwd=spec.cwd,
            stdout=log or subprocess.DEVNULL,
            stderr=log or subprocess.DEVNULL,
            start_new_session=True)
    except OSError as exc:
        raise ProxyError(f"could not start proxy {argv[0]}: {exc}") from exc
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise ProxyError(
                f"proxy exited early (rc={proc.returncode}): "
                f"{' '.join(argv)}")
        if _healthy(spec, timeout=1.0):
            return proc
        time.sleep(0.25)
    try:
        stop_proxy(proc, timeout=5.0)
    except Exception:
        pass
    raise ProxyError(
        f"proxy did not become healthy on port {spec.port} within "
        f"{timeout}s: {' '.join(argv)}")


def stop_proxy(proc, timeout=10.0):
    """Terminate a proxy started by start_proxy; kill if stubborn."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout)


# ---------------------------------------------------------------------------
# Generic OpenAI-compatible proxy server (serve mode)
# ---------------------------------------------------------------------------

def _make_handler(base, credential, allowed, model, port,
                  add_surrogate):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, status, body, ctype="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def do_GET(self):
            if self.path in ("/v1/models", "/models"):
                req = urllib.request.Request(base + "/models", method="GET")
                add_surrogate(req, credential, allowed_hosts=allowed)
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        self._send(resp.status, resp.read())
                except urllib.error.HTTPError as e:
                    self._send(e.code, e.read())
                return
            if self.path in ("/", "/health"):
                self._send(200, json.dumps(
                    {"ok": True, "arm_model": model}).encode())
                return
            self._send(404, b"{}")

        def do_POST(self):
            if self.path not in ("/v1/chat/completions",
                                 "/chat/completions"):
                self._send(404, b"{}")
                return
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n)
            try:
                payload = json.loads(raw.decode())
            except Exception:
                self._send(400, b'{"error": "bad json"}')
                return
            payload["model"] = model
            is_stream = bool(payload.get("stream"))
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                base + "/chat/completions", data=body,
                headers={"Content-Type": "application/json"},
                method="POST")
            add_surrogate(req, credential, allowed_hosts=allowed)
            try:
                resp = urllib.request.urlopen(req, timeout=300)
            except urllib.error.HTTPError as e:
                self._send(e.code, e.read())
                return
            except Exception as e:
                self._send(502, json.dumps(
                    {"error": str(e)[:200]}).encode())
                return
            if is_stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    for line in resp:
                        self.wfile.write(line)
                        self.wfile.flush()
                finally:
                    resp.close()
                    self.close_connection = True
                return
            data = resp.read()
            try:
                usage = json.loads(data.decode()).get("usage")
            except Exception:
                usage = None
            sys.stderr.write(f"chat status={resp.status} usage={usage}\n")
            sys.stderr.flush()
            self._send(resp.status, data)

    return H


def serve(port, arm, model):
    """Run the generic proxy in the foreground (serve mode)."""
    sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
    try:
        from dynamic_credentials import add_surrogate_to_request
    except ImportError as exc:
        raise ProxyError(
            "dynamic_credentials is not importable on this machine; "
            "the generic proxy cannot run here") from exc
    base, credential, allowed = ARMS[arm]
    handler = _make_handler(base, credential, allowed, model, port,
                            add_surrogate_to_request)
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    sys.stderr.write(
        f"proxy up 127.0.0.1:{port} arm={arm} model={model}\n")
    sys.stderr.flush()
    srv.serve_forever()


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="live_proxy",
        description="Generic OpenAI-compatible proxy for live runs.")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="run the proxy in the foreground")
    s.add_argument("--port", type=int, required=True)
    s.add_argument("--arm", choices=list(ARMS), required=True)
    s.add_argument("--model", required=True)
    args = ap.parse_args(argv)
    if args.command == "serve":
        serve(args.port, args.arm, args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
