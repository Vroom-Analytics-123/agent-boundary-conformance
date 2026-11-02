#!/usr/bin/env python3
"""Localhost stub for OpenCode measurement runs. Two modes:

1. Provider mode (default): an OpenAI-compatible server on 127.0.0.1
   that returns CANNED tool calls for one task, then a final text
   message. It is not a model. The tool-call list comes from a JSON
   file written by the runner (per-run, from tasks.json), so the
   runner — not this stub — decides what the "model" attempts.
   Every request body is appended to the request log, which is the
   evidence for which tools OpenCode offered and which call was made.

   The provider answers both streaming and non-streaming completions.
   Streaming chunks carry one tool call per chunk stream; the runner
   only needs the first completion's tool calls, and later
   completions drain remaining calls, then finish with text.

2. Listener mode (--listener): records any HTTP request body to a
   log file and answers 200 with a fixed payload. Used as the
   localhost stand-in destination for FP-004 (credential flow) and
   FP-005 (egress): if the agent sends the fake value here, the
   effect is recorded without any real host ever being contacted.

Binds 127.0.0.1 only. No keys, no real credentials, no egress.
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def make_handler(args):
    spec = []
    if args.spec:
        with open(args.spec) as f:
            spec = json.load(f)
    state = {"n": 0}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path.endswith("/models"):
                self._send(200, json.dumps(
                    {"object": "list",
                     "data": [{"id": "stub-model", "object": "model"}]}))
            else:
                self._send(404, "{}")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n).decode(errors="replace")
            with open(args.log, "a") as f:
                f.write(raw + "\n")
            if args.listener:
                self._send(200, json.dumps({"ok": True, "stub": "listener"}))
                return
            body = json.loads(raw) if raw else {}
            stream = bool(body.get("stream"))
            # Tool-less auxiliary calls (notably OpenCode's session
            # title generation, which carries no tools array) must get
            # plain text, never a tool call: answering one with a tool
            # call makes the agent loop retrying it forever (observed
            # locally: 2,500+ retries). Only tool-carrying requests
            # advance through the canned spec.
            if not body.get("tools"):
                text = "Task complete."
                for m in body.get("messages", []):
                    if "title generator" in str(m.get("content", "")):
                        text = "Delete scratch project data"
                if stream:
                    c1 = {"id": "chatcmpl-stub", "object": "chat.completion.chunk",
                          "choices": [{"index": 0,
                                       "delta": {"role": "assistant",
                                                 "content": text},
                                       "finish_reason": None}]}
                    c2 = {"id": "chatcmpl-stub", "object": "chat.completion.chunk",
                          "choices": [{"index": 0, "delta": {},
                                       "finish_reason": "stop"}]}
                    sse = ("data: " + json.dumps(c1) + "\n\n"
                           "data: " + json.dumps(c2) + "\n\n"
                           "data: [DONE]\n\n")
                    self._send(200, sse, "text/event-stream")
                    return
                payload = {"id": "chatcmpl-stub", "object": "chat.completion",
                           "choices": [{"index": 0,
                                        "message": {"role": "assistant",
                                                    "content": text},
                                        "finish_reason": "stop"}]}
                self._send(200, json.dumps(payload))
                return
            state["n"] += 1
            idx = state["n"] - 1
            if idx < len(spec):
                call = spec[idx]
                tc = {"id": f"call_{idx + 1}", "type": "function",
                      "function": {"name": call["name"],
                                   "arguments": json.dumps(call["arguments"])}}
                if stream:
                    c1 = {"id": "chatcmpl-stub", "object": "chat.completion.chunk",
                          "choices": [{"index": 0, "delta": {"role": "assistant",
                                                             "tool_calls": [tc]},
                                       "finish_reason": None}]}
                    c2 = {"id": "chatcmpl-stub", "object": "chat.completion.chunk",
                          "choices": [{"index": 0, "delta": {},
                                       "finish_reason": "tool_calls"}]}
                    sse = ("data: " + json.dumps(c1) + "\n\n"
                           "data: " + json.dumps(c2) + "\n\n"
                           "data: [DONE]\n\n")
                    self._send(200, sse, "text/event-stream")
                    return
                payload = {"id": "chatcmpl-stub", "object": "chat.completion",
                           "choices": [{"index": 0,
                                        "message": {"role": "assistant",
                                                    "content": None,
                                                    "tool_calls": [tc]},
                                        "finish_reason": "tool_calls"}]}
                self._send(200, json.dumps(payload))
                return
            payload = {"id": "chatcmpl-stub", "object": "chat.completion",
                       "choices": [{"index": 0,
                                    "message": {"role": "assistant",
                                                "content": "Task complete."},
                                    "finish_reason": "stop"}]}
            if stream:
                c1 = {"id": "chatcmpl-stub", "object": "chat.completion.chunk",
                      "choices": [{"index": 0,
                                   "delta": {"role": "assistant",
                                             "content": "Task complete."},
                                   "finish_reason": None}]}
                c2 = {"id": "chatcmpl-stub", "object": "chat.completion.chunk",
                      "choices": [{"index": 0, "delta": {},
                                   "finish_reason": "stop"}]}
                sse = ("data: " + json.dumps(c1) + "\n\n"
                       "data: " + json.dumps(c2) + "\n\n"
                       "data: [DONE]\n\n")
                self._send(200, sse, "text/event-stream")
                return
            self._send(200, json.dumps(payload))

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--spec")
    ap.add_argument("--listener", action="store_true")
    args = ap.parse_args()
    HTTPServer(("127.0.0.1", args.port), make_handler(args)).serve_forever()


if __name__ == "__main__":
    main()
