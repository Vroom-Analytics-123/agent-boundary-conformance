import os, sys, json
HOME=os.path.expanduser("~")
SB=os.path.join(HOME,"workspace/agent-boundary-conformance-live-sandbox-openclaw")
EXCL=[SB, os.path.join(HOME,".npm"), os.path.join(HOME,".cache"), os.path.join(HOME,"agents"), os.path.join(HOME,"workspace/agents"), os.path.join(HOME,"workspace/agent-boundary-conformance/evidence/live-campaign-2026-10-23"), os.path.join(HOME,"workspace/agent-boundary-conformance/docs/fixes")]
snap={}
for root,dirs,files in os.walk(HOME, followlinks=False):
    ar=os.path.abspath(root)
    if any(ar==e or ar.startswith(e+os.sep) for e in EXCL): dirs[:]=[]; continue
    dirs[:]=[d for d in dirs if not any(os.path.abspath(os.path.join(root,d))==e or os.path.abspath(os.path.join(root,d)).startswith(e+os.sep) for e in EXCL)]
    for n in files:
        p=os.path.join(root,n)
        try: st=os.lstat(p)
        except OSError: continue
        snap[p]=(st.st_size, st.st_mtime_ns)
json.dump(snap, open(sys.argv[1],"w"))
print("snapshot entries", len(snap))
