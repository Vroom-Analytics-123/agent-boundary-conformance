import sys, os, urllib.request
sys.path.insert(0,"/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request
req=urllib.request.Request("https://api.cheaperinference.com/v1/chat/completions")
add_surrogate_to_request(req,"custom.cheaperinference",allowed_hosts=["api.cheaperinference.com"])
auth=req.headers.get("Authorization","")
assert auth.startswith("Bearer ") and len(auth)>10, "surrogate mint failed"
os.environ["CHEAPERINFERENCE_API_KEY"]=auth[len("Bearer "):]
SB=os.path.expanduser("~/workspace/agent-boundary-conformance-live-sandbox-openclaw")
os.environ["OPENCLAW_HOME"]=SB+"/home"
os.environ["OPENCLAW_STATE_DIR"]=SB+"/home/.openclaw"
os.environ["OPENCLAW_CONFIG_PATH"]=SB+"/home/.openclaw/openclaw.json"
print("launcher: key minted in-memory, env set (value not printed), exec gateway", flush=True)
os.execvpe("/home/hatch/workspace/agent-boundary-conformance-live-sandbox-openclaw/evidence-staging/scripts/oc.sh", ["openclaw","gateway","run","--port","18901"], os.environ)
