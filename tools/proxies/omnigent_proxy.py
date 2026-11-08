#!/usr/bin/env python3
# PROVENANCE (live-runner framework, 2026-11-07): Vendored 2026-11-07 into the live-runner framework from ~/workspace/omnigent-live-v1/proxy_fresh.py. Body is verbatim; only this header was added. --port required (8893 cheaper / 8894 meta); GET /health returns {"status": "ok"}. Used by adapters/omnigent.live.yaml.
"""Fresh minimal OpenAI-compatible proxy for Omnigent live measurement.

Written from scratch for this task (not copied from any prior rollout).
Agents talk to 127.0.0.1 only. The proxy rewrites ONLY the `model` field
to the arm model and forwards everything else verbatim to the provider's
/v1/chat/completions, authenticating through the dynamic-credentials
surrogate helper. No raw credential ever appears in this file, in logs,
or in any agent environment. Agent processes hold only a dummy string.

Usage:
  proxy_fresh.py --port 8893 --arm cheaper --model beam-free
  proxy_fresh.py --port 8894 --arm meta --model muse-spark-1.1
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

UA = "Mozilla/5.0 (X11; Linux x86_64) FinePrint-measurement-proxy"


def make_handler(base, credential, allowed, model):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, status, body, ctype="application/json"):
            try:
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.close_connection = True

        def _forward(self, path, data):
            req = urllib.request.Request(
                base + path, data=data, method="POST",
                headers={"Content-Type": "application/json",
                         "User-Agent": UA})
            add_surrogate_to_request(req, credential, allowed_hosts=allowed)
            try:
                resp = urllib.request.urlopen(req, timeout=300)
                return resp.status, resp
            except urllib.error.HTTPError as e:
                return e.code, e
            except Exception as e:  # noqa: BLE001 - surfaced to caller as 502
                return 502, e

        def do_GET(self):
            if self.path in ("/", "/health"):
                self._send(200, json.dumps(
                    {"ok": True, "arm_model": model}).encode())
                return
            if self.path in ("/v1/models", "/models"):
                req = urllib.request.Request(
                    base + "/models", method="GET",
                    headers={"User-Agent": UA})
                add_surrogate_to_request(req, credential,
                                         allowed_hosts=allowed)
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        self._send(resp.status, resp.read())
                except urllib.error.HTTPError as e:
                    self._send(e.code, e.read())
                except Exception as e:  # noqa: BLE001
                    self._send(502, json.dumps(
                        {"error": str(e)[:200]}).encode())
                return
            if self.path.startswith(("/v1/responses/", "/responses/")):
                fwd = ("/responses/" + self.path.split("/responses/", 1)[1])
                req = urllib.request.Request(
                    base + fwd, method="GET",
                    headers={"User-Agent": UA})
                add_surrogate_to_request(req, credential,
                                         allowed_hosts=allowed)
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        self._send(resp.status, resp.read())
                except urllib.error.HTTPError as e:
                    self._send(e.code, e.read())
                except Exception as e:  # noqa: BLE001
                    self._send(502, json.dumps(
                        {"error": str(e)[:200]}).encode())
                return
            self._send(404, b"{}")

        def do_POST(self):
            if self.path in ("/v1/chat/completions",
                             "/chat/completions"):
                fwd_path = "/chat/completions"
            elif self.path in ("/v1/responses", "/responses"):
                fwd_path = "/responses"
            else:
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
            status, resp = self._forward(fwd_path,
                                         json.dumps(payload).encode())
            sys.stderr.write(
                f"proxy chat status={status} arm_model={model} "
                f"stream={is_stream}\n")
            sys.stderr.flush()
            if status == 502 and not hasattr(resp, "read"):
                self._send(502, json.dumps(
                    {"error": str(resp)[:200]}).encode())
                return
            if is_stream and status == 200:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    for line in resp:
                        self.wfile.write(line)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    try:
                        resp.close()
                    except Exception:
                        pass
                    self.close_connection = True
                return
            try:
                body = resp.read()
            except Exception as e:  # noqa: BLE001
                body = json.dumps({"error": str(e)[:200]}).encode()
                status = 502
            self._send(status, body)

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--arm", choices=list(ARMS), required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    base, credential, allowed = ARMS[args.arm]
    srv = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        make_handler(base, credential, allowed, args.model))
    sys.stderr.write(f"proxy up 127.0.0.1:{args.port} arm={args.arm} "
                     f"model={args.model}\n")
    sys.stderr.flush()
    srv.serve_forever()


if __name__ == "__main__":
    main()
