// OpenClaw Gateway operator client (FinePrint v1 measurement).
// Connects as an operator client declaring the approvals capability and
// stays connected for the duration of one agent turn. Its presence is what
// makes the gateway WAIT on exec approvals (pending) instead of instantly
// denying headless turns (askFallback=deny). It does NOT resolve anything:
// resolutions are issued by the driver's CLI polling loop (deny-only),
// exactly as the Oct 23 keystone driver did.
// Retries across gateway startup (UNAVAILABLE/startup-sidecars) and socket
// closes until the driver kills it.
// Usage: node openclaw_ws_client.mjs <gateway-port> <events-out.jsonl>
import fs from "node:fs";

const port = process.argv[2];
const outPath = process.argv[3];
const log = (obj) => {
  fs.appendFileSync(outPath, JSON.stringify({ at: new Date().toISOString(), ...obj }) + "\n");
};

let reqId = 0;
let stopped = false;

function connectOnce() {
  if (stopped) return;
  const ws = new WebSocket(`ws://127.0.0.1:${port}`);
  const pendingReqs = new Map();
  let connected = false;
  let helloDone = false;
  function send(method, params) {
    const id = "r" + ++reqId;
    return new Promise((resolve) => {
      pendingReqs.set(id, resolve);
      ws.send(JSON.stringify({ type: "req", id, method, params }));
    });
  }
  async function doConnect() {
    if (helloDone) return;
    helloDone = true;
    try {
      const res = await send("connect", {
        minProtocol: 4, maxProtocol: 4,
        client: { id: "gateway-client", version: "2026.10.6", platform: "linux", mode: "backend" },
        role: "operator",
        scopes: ["operator.read", "operator.write", "operator.approvals", "operator.admin"],
        caps: ["approvals", "exec-approvals"],
        locale: "en-US",
        userAgent: "fineprint-measurement-driver/2026.10.6",
      });
      log({ kind: "hello", ok: res.ok, error: res.error || null });
      connected = res.ok;
      if (!res.ok) { try { ws.close(); } catch {} }
    } catch (e) {
      log({ kind: "hello-error", message: String(e.message || e) });
      try { ws.close(); } catch {}
    }
  }
  ws.addEventListener("open", () => log({ kind: "ws-open" }));
  ws.addEventListener("error", (e) => log({ kind: "ws-error", message: String(e.message || e) }));
  ws.addEventListener("close", (e) => {
    log({ kind: "ws-close", code: e.code, wasConnected: connected });
    if (!stopped) setTimeout(connectOnce, 2000);
  });
  ws.addEventListener("message", async (ev) => {
    let frame;
    try { frame = JSON.parse(ev.data); } catch { return; }
    if (frame.type === "res" && pendingReqs.has(frame.id)) {
      pendingReqs.get(frame.id)(frame); pendingReqs.delete(frame.id); return;
    }
    if (frame.type === "event" && frame.event === "connect.challenge" && !connected) {
      doConnect(); return;
    }
    if (frame.type === "event") {
      log({ kind: "event", event: frame.event,
            payload: JSON.stringify(frame.payload || {}).slice(0, 500) });
    }
  });
  setTimeout(() => { if (!connected) doConnect(); }, 4000);
}

process.on("SIGTERM", () => { stopped = true; process.exit(0); });
process.on("SIGINT", () => { stopped = true; process.exit(0); });
log({ kind: "client-started", port });
connectOnce();
setInterval(() => {}, 30000);
