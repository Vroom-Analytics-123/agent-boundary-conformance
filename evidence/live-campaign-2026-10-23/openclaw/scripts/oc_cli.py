import sys, os, urllib.request, subprocess
sys.path.insert(0,"/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request
req=urllib.request.Request("https://api.cheaperinference.com/v1/chat/completions")
add_surrogate_to_request(req,"custom.cheaperinference",allowed_hosts=["api.cheaperinference.com"])
auth=req.headers.get("Authorization","")
os.environ["CHEAPERINFERENCE_API_KEY"]=auth[len("Bearer "):]
SB=os.path.expanduser("~/workspace/agent-boundary-conformance-live-sandbox-openclaw")
os.environ.setdefault("OPENCLAW_HOME", SB+"/home")
os.environ.setdefault("OPENCLAW_STATE_DIR", SB+"/home/.openclaw")
os.environ.setdefault("OPENCLAW_CONFIG_PATH", SB+"/home/.openclaw/openclaw.json")
r=subprocess.run(["/home/hatch/workspace/agent-boundary-conformance-live-sandbox-openclaw/evidence-staging/scripts/oc.sh"]+sys.argv[1:], env=os.environ)
sys.exit(r.returncode)
