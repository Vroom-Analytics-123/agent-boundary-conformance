// OpenClaw Gateway approval client (FinePrint Stage 4 driver surface).
// Connects as an operator client declaring the approvals capability, logs
// every exec.approval.requested event verbatim (A4), and resolves each one
// with the decision matched from the decision-map file (A3 driver).
// Usage: node approval_client.mjs <decision-map.json> <events-out.jsonl>
// Decision map: [{"match": "<substring of stringified request>", "decision": "allow-once|allow-always|deny"}]
import fs from "node:fs";

const mapPath = process.argv[2];
const outPath = process.argv[3];
const decisions = JSON.parse(fs.readFileSync(mapPath, "utf8"));
const log = (obj) => {
  fs.appendFileSync(outPath, JSON.stringify({ at: new Date().toISOString(), ...obj }) + "\n");
  console.log(JSON.stringify(obj).slice(0, 400));
};

const ws = new WebSocket("ws://127.0.0.1:18901");
let reqId = 0;
const pendingReqs = new Map();
function send(method, params) {
  const id = "r" + ++reqId;
  return new Promise((resolve) => {
    pendingReqs.set(id, resolve);
    ws.send(JSON.stringify({ type: "req", id, method, params }));
  });
}

ws.addEventListener("open", () => log({ kind: "ws-open" }));
ws.addEventListener("error", (e) => log({ kind: "ws-error", message: String(e.message || e) }));
ws.addEventListener("close", (e) => { log({ kind: "ws-close", code: e.code, reason: e.reason }); process.exit(3); });

let connected = false;
async function doConnect() {
  const res = await send("connect", {
    minProtocol: 4, maxProtocol: 4,
    client: { id: "gateway-client", version: "2026.10.6", platform: "linux", mode: "backend" },
    role: "operator",
    scopes: ["operator.read", "operator.write", "operator.approvals", "operator.admin"],
    caps: ["approvals", "exec-approvals"],
    locale: "en-US",
    userAgent: "fineprint-approval-driver/2026.10.6",
  });
  log({ kind: "hello", ok: res.ok, payload: res.payload ? {
    protocol: res.payload.protocol, server: res.payload.server,
    auth: res.payload.auth } : res.error });
  connected = res.ok;
  if (res.ok) {
    const list = await send("exec.approval.list", {});
    log({ kind: "backfill", ok: list.ok, payload: list.payload ?? list.error });
  }
}

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
    log({ kind: "event", event: frame.event, payload: frame.payload });
    if (frame.event === "exec.approval.requested") {
      const p = frame.payload || {};
      const id = p.id || p.approvalId || p.requestId;
      const text = JSON.stringify(p);
      const rule = decisions.find((d) => text.includes(d.match));
      if (!id) { log({ kind: "resolve-skip", reason: "no id in payload", payload: p }); return; }
      if (!rule) { log({ kind: "resolve-skip", reason: "no decision rule matched", id }); return; }
      const res = await send("exec.approval.resolve", { id, decision: rule.decision });
      log({ kind: "resolve", id, decision: rule.decision, ok: res.ok, payload: res.payload ?? res.error });
      if (!res.ok) {
        // No unified-resolve fallback: an earlier version's fallback silently
        // landed as a recorded "deny". Log the failure, then clean up with an
        // explicit exec.approval.resolve deny so the agent turn can finish.
        const res2 = await send("exec.approval.resolve", { id, decision: "deny" });
        log({ kind: "resolve-cleanup-deny", id, intendedDecision: rule.decision, ok: res2.ok, payload: res2.payload ?? res2.error });
      }
    }
  }
});

setTimeout(() => { if (!connected) doConnect(); }, 4000);
setInterval(() => {}, 30000);
log({ kind: "client-started", map: mapPath });
