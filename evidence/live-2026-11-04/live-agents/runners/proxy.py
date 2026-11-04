#!/usr/bin/env python3
"""Local OpenAI-compatible proxy for FinePrint live-agent measurement.

Agents talk to 127.0.0.1 only. The proxy forwards each request body to
the provider's /v1/chat/completions, rewriting ONLY the `model` field
to the arm model; everything else goes verbatim. Auth uses the
dynamic-credential surrogate helper exactly as the connector CLIs do:
no raw key ever appears in chat, files, logs, or agent environments.
Agent processes hold no credentials at all.

Usage:
  proxy.py --port 8891 --arm cheaper --model beam-free
  proxy.py --port 8892 --arm meta --model muse-spark-1.1
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

ARMS = {
    "cheaper": ("https://api.cheaperinference.com/v1",
                "custom.cheaperinference", ["api.cheaperinference.com"]),
    "meta": ("https://api.meta.ai/v1",
             "custom.meta-model-api", ["api.meta.ai"]),
}


def make_handler(base, credential, allowed, model, port):
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
                add_surrogate_to_request(req, credential, allowed_hosts=allowed)
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        self._send(resp.status, resp.read())
                except urllib.error.HTTPError as e:
                    self._send(e.code, e.read())
                return
            if self.path in ("/", "/health"):
                self._send(200, json.dumps({"ok": True, "arm_model": model}).encode())
                return
            self._send(404, b"{}")

        def do_POST(self):
            if self.path not in ("/v1/chat/completions", "/chat/completions"):
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
            if os.environ.get("PROXY_DEBUG_BODY"):
                try:
                    with open(f"/tmp/proxy-debug-{port}.jsonl", "a") as df:
                        df.write(json.dumps(payload)[:500000] + "\n")
                except Exception:
                    pass
            is_stream = bool(payload.get("stream"))
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                base + "/chat/completions", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            add_surrogate_to_request(req, credential, allowed_hosts=allowed)
            try:
                resp = urllib.request.urlopen(req, timeout=300)
            except urllib.error.HTTPError as e:
                self._send(e.code, e.read())
                return
            except Exception as e:
                self._send(502, json.dumps({"error": str(e)[:200]}).encode())
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--arm", choices=list(ARMS), required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    base, credential, allowed = ARMS[args.arm]
    srv = ThreadingHTTPServer(("127.0.0.1", args.port),
                              make_handler(base, credential, allowed, args.model, args.port))
    sys.stderr.write(f"proxy up 127.0.0.1:{args.port} arm={args.arm} model={args.model}\n")
    sys.stderr.flush()
    srv.serve_forever()


if __name__ == "__main__":
    main()
