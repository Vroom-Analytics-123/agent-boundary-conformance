#!/usr/bin/env python3
# PROVENANCE (live-runner framework, 2026-11-07): Vendored 2026-11-07 into the live-runner framework from ~/workspace/gemini-cli-cheaper/translator/proxy.py. Body is verbatim; only this header was added. Default port 8897 (--port); GET / returns {"status": "ok"}. Used by adapters/gemini-cli.live.yaml.
"""Gemini -> OpenAI translating proxy for Gemini CLI harness measurement.

Listens on localhost only. Accepts the Gemini API request shape the CLI
emits (POST /v1beta/models/<model>:generateContent and
:streamGenerateContent) and forwards the equivalent OpenAI chat-completions
request to cheaperinference. Translates the response back to the Gemini
shape.

FIXED MODEL (owner guardrail): the model used for every cell of this
harness's series is FIXED here, not taken from the request path. The path
model is logged (and a warning logged if it differs) but never used
upstream. Changing the model is a new series, never a mid-series swap.

    FIXED_MODEL = "gemini-2.5-flash"   # Flash, not flash-lite: capability
                                       # floor for a meaningful run (a model
                                       # that actually attempts tasks and
                                       # makes tool calls, so harness
                                       # signal is observable).

Auth: the CLI process holds only a dummy key (GEMINI_API_KEY=dummy-local-only).
The real cheaperinference credential reaches upstream ONLY through the
connector surrogate (dynamic_credentials, credential "custom.cheaperinference",
allowed host api.cheaperinference.com) — exactly the ci.py pattern. This
file never reads, prints, logs, or stores any credential value. Incoming
auth headers are ignored and never logged; upstream error bodies are logged
truncated (they contain no credentials).

Translation notes (mechanism, not magic):
- Gemini contents -> OpenAI messages: role user->user, model->assistant.
  Text parts concatenate into content; functionCall parts become tool_calls
  with proxy-synthesized ids (call_1, call_2, ...). functionResponse parts
  become tool messages; the id is popped from a per-function-name FIFO queue
  filled when the proxy last issued that function's calls (the Gemini wire
  format carries no call id on the response side). If the queue is empty, a
  fresh id is synthesized and a warning logged. Sequential CLI turns only;
  concurrent conversations would interleave the queues (not used here).
- systemInstruction -> leading system message.
- tools[].functionDeclarations -> OpenAI tools[{type:function,...}].
- toolConfig.functionCallingConfig.mode: AUTO/ANY -> "auto", NONE -> "none"
  (ANY is deliberately NOT mapped to OpenAI "required": forcing a call
  would distort the harness signal; the model choosing to call is the
  observable behavior).
- generationConfig: temperature -> temperature, maxOutputTokens ->
  max_tokens, topP -> top_p, stopSequences -> stop. topK has no OpenAI
  equivalent and is dropped (logged).
- Upstream is ALWAYS called non-streaming (stream=false), even for
  :streamGenerateContent. The translated response is returned as a single
  SSE data event, which the CLI accepts as a complete stream turn (verified
  against a logging stub before this proxy was built). This avoids
  incremental tool-call argument accumulation across SSE deltas.
- OpenAI finish_reason mapping: stop/tool_calls -> STOP, length ->
  MAX_TOKENS, content_filter -> SAFETY, anything else -> STOP.
- Usage maps to usageMetadata (prompt/candidates/total token counts).

Limitations (honest):
- One fixed model, sequential turns, no vision/audio parts (text +
  function calls only; any other part kind is logged and dropped).
- The proxy does not evaluate policy or approval; it only translates.
  All harness behavior (deny rules, approval gates) happens in the CLI.
"""
import argparse
import itertools
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response  # noqa: E402

FIXED_MODEL = "gemini-2.5-flash"
UPSTREAM = "https://api.cheaperinference.com/v1/chat/completions"
CREDENTIAL = "custom.cheaperinference"
ALLOWED = ["api.cheaperinference.com"]

_counter = itertools.count(1)
_lock = threading.Lock()
_pending_ids = {}  # function name -> FIFO list of issued call ids


def log(msg):
    print(msg, flush=True)


def _pop_id(name):
    with _lock:
        q = _pending_ids.get(name, [])
        if q:
            return q.pop(0)
    log(f"WARN: no pending id for function {name!r}; synthesizing")
    return f"call_{next(_counter)}"


def _push_id(name, cid):
    with _lock:
        _pending_ids.setdefault(name, []).append(cid)


def gemini_to_openai(body):
    """Return (openai_payload, warnings)."""
    warnings = []
    messages = []
    sys_inst = body.get("systemInstruction") or {}
    for part in sys_inst.get("parts", []):
        if "text" in part:
            messages.append({"role": "system", "content": part["text"]})
    for content in body.get("contents", []):
        role = content.get("role", "user")
        texts, tool_calls = [], []
        for part in content.get("parts", []):
            if "text" in part:
                texts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                cid = f"call_{next(_counter)}"
                _push_id(fc.get("name", ""), cid)
                tool_calls.append({
                    "id": cid, "type": "function",
                    "function": {"name": fc.get("name", ""),
                                 "arguments": json.dumps(fc.get("args", {}))},
                })
            elif "functionResponse" in part:
                fr = part["functionResponse"]
                name = fr.get("name", "")
                resp = fr.get("response", {})
                messages.append({
                    "role": "tool",
                    "tool_call_id": _pop_id(name),
                    "content": json.dumps(resp) if not isinstance(resp, str) else resp,
                })
            else:
                warnings.append(f"dropped unknown part kind: {sorted(part.keys())}")
        if texts or tool_calls:
            msg = {"role": "assistant" if role == "model" else "user"}
            if texts:
                msg["content"] = "\n".join(texts)
            if tool_calls:
                msg["tool_calls"] = tool_calls
            messages.append(msg)
    tools = []
    for tool in body.get("tools", []):
        for decl in tool.get("functionDeclarations", []):
            params = decl.get("parameters") or {}
            tools.append({"type": "function", "function": {
                "name": decl.get("name", ""),
                "description": decl.get("description", ""),
                "parameters": params,
            }})
    payload = {"model": FIXED_MODEL, "messages": messages}
    if tools:
        payload["tools"] = tools
    cfg = body.get("toolConfig", {}).get("functionCallingConfig", {})
    mode = str(cfg.get("mode", "")).upper()
    if mode in ("AUTO", "ANY"):
        payload["tool_choice"] = "auto"
    elif mode == "NONE":
        payload["tool_choice"] = "none"
    gen = body.get("generationConfig", {})
    if "temperature" in gen:
        payload["temperature"] = gen["temperature"]
    if "maxOutputTokens" in gen:
        payload["max_tokens"] = gen["maxOutputTokens"]
    if "topP" in gen:
        payload["top_p"] = gen["topP"]
    if "topK" in gen:
        warnings.append("dropped topK (no OpenAI equivalent)")
    if "stopSequences" in gen:
        payload["stop"] = gen["stopSequences"]
    return payload, warnings


def openai_to_gemini(resp):
    """Return a Gemini GenerateContentResponse dict."""
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    parts = []
    if msg.get("content"):
        parts.append({"text": msg["content"]})
    for tc in msg.get("tool_calls", []) or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}") or "{}")
        except json.JSONDecodeError:
            log(f"WARN: unparseable tool args for {fn.get('name')!r}; using empty args")
            args = {}
        if not isinstance(args, dict):
            args = {"value": args}
        parts.append({"functionCall": {"name": fn.get("name", ""), "args": args}})
    fr = choice.get("finish_reason", "stop")
    finish = {"length": "MAX_TOKENS", "content_filter": "SAFETY"}.get(fr, "STOP")
    out = {"candidates": [{"content": {"role": "model", "parts": parts},
                           "finishReason": finish}]}
    usage = resp.get("usage") or {}
    if usage:
        out["usageMetadata"] = {
            "promptTokenCount": usage.get("prompt_tokens", 0),
            "candidatesTokenCount": usage.get("completion_tokens", 0),
            "totalTokenCount": usage.get("total_tokens", 0),
        }
    return out


def call_upstream(payload):
    req = urllib.request.Request(
        UPSTREAM, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    add_surrogate_to_request(req, CREDENTIAL, allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, read_json_response(r)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")[:1000]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, body_bytes, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        if self.path == "/":
            self._send(200, b'{"ok":true,"proxy":"gemini-to-openai"}', "application/json")
        else:
            self._send(404, b'{"error":"unknown path"}', "application/json")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self._send(400, b'{"error":"bad json"}', "application/json")
            return
        streaming = "streamGenerateContent" in self.path
        path_model = self.path.split("/models/")[-1].split(":")[0] if "/models/" in self.path else "?"
        if path_model != FIXED_MODEL:
            log(f"NOTE: path model {path_model!r} != fixed model; using {FIXED_MODEL!r}")
        payload, warnings = gemini_to_openai(body)
        for w in warnings:
            log(f"WARN: {w}")
        log(f"REQ path_model={path_model} msgs={len(payload['messages'])} "
            f"tools={len(payload.get('tools', []))} "
            f"tool_names={[t['function']['name'] for t in payload.get('tools', [])]} "
            f"tool_msgs={sum(1 for m in payload['messages'] if m.get('role') == 'tool')} "
            f"streaming={streaming}")
        status, resp = call_upstream(payload)
        if status != 200:
            log(f"UPSTREAM ERROR {status}: {json.dumps(resp)[:500]}")
            self._send(502, json.dumps({"error": "upstream failure",
                                        "status": status}).encode(), "application/json")
            return
        gem = openai_to_gemini(resp)
        data = json.dumps(gem).encode()
        if streaming:
            sse = b"data: " + data + b"\n\n"
            self._send(200, sse, "text/event-stream")
        else:
            self._send(200, data, "application/json")
        nparts = len(gem["candidates"][0]["content"]["parts"])
        kinds = [sorted(p.keys()) for p in gem["candidates"][0]["content"]["parts"]]
        fcnames = [p["functionCall"]["name"] for p in gem["candidates"][0]["content"]["parts"] if "functionCall" in p]
        log(f"RESP parts={nparts} kinds={kinds} functionCalls={fcnames} finish={gem['candidates'][0]['finishReason']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8897)
    a = ap.parse_args()
    log(f"translator listening on 127.0.0.1:{a.port}, fixed model {FIXED_MODEL}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
