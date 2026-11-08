#!/usr/bin/env python3
# PROVENANCE (live-runner framework, 2026-11-07): Vendored 2026-11-07 into the live-runner framework from ~/workspace/claudecode-fresh/proxy.py (the Nov 4 Claude Code clean rebuild). Body is verbatim; only this header was added. Fixed port 8898; no HTTP health endpoint (TCP connect only). Used by adapters/claude-code.live.yaml.
"""Fresh pass-through proxy for the Claude Code clean rebuild (Nov 4, 2026).

Forwards Anthropic-format requests from the local Claude Code CLI to
https://api.cheaperinference.com/v1 with NO translation (cheaperinference
accepts Anthropic format natively). The CLI holds only a dummy key; this
proxy attaches the real credential ONLY via the connector-surrogate pattern
(dynamic_credentials), so no credential value ever appears in any file, log,
or record produced here.

Logging is minimal on purpose: method + path + upstream status only. No
headers and no bodies are ever logged.
"""

import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request

UPSTREAM = "https://api.cheaperinference.com"
PORT = 8898

# Hop-by-hop / auth headers: never forwarded from the client. The dummy key
# the CLI holds is stripped here; the surrogate is attached instead.
SKIP_HEADERS = {
    "host",
    "authorization",
    "x-api-key",
    "content-length",
    "connection",
    "transfer-encoding",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        url = UPSTREAM + self.path
        req = urllib.request.Request(url, data=body, method=self.command)
        for key, value in self.headers.items():
            if key.lower() in SKIP_HEADERS:
                continue
            req.add_header(key, value)
        if body and not req.has_header("Content-Type"):
            req.add_header("Content-Type", "application/json")
        try:
            add_surrogate_to_request(
                req,
                "custom.cheaperinference",
                allowed_hosts=["api.cheaperinference.com"],
            )
        except Exception as exc:  # surrogate failure: fail closed, no retry
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(
                json.dumps({"error": "proxy credential unavailable"}).encode()
            )
            sys.stderr.write(f"{self.command} {self.path} SURROGATE_FAIL {exc}\n")
            sys.stderr.flush()
            return
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self.send_response(resp.status)
                for key, value in resp.headers.items():
                    if key.lower() in (
                        "transfer-encoding",
                        "connection",
                        "content-length",
                    ):
                        continue
                    self.send_header(key, value)
                # Close-delimited body: upstream chunk framing is decoded by
                # urllib, so the client learns the end from connection close.
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            sys.stderr.write(f"{self.command} {self.path} {resp.status}\n")
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(payload)
            sys.stderr.write(f"{self.command} {self.path} {exc.code}\n")
        except Exception as exc:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(
                json.dumps({"error": "proxy upstream failure"}).encode()
            )
            sys.stderr.write(f"{self.command} {self.path} UPSTREAM_FAIL {exc}\n")
        sys.stderr.flush()

    do_GET = _forward
    do_POST = _forward
    do_PUT = _forward
    do_DELETE = _forward

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    sys.stderr.write(f"proxy listening 127.0.0.1:{PORT}\n")
    sys.stderr.flush()
    server.serve_forever()
