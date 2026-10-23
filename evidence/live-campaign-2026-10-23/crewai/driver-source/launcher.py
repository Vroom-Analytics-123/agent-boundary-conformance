#!/usr/bin/env python3
"""Campaign launcher: obtain the CheaperInference gateway key via the
approved dynamic-credentials surrogate flow and exec the CrewAI runner
with the key ONLY in the child process environment (OPENAI_API_KEY).
The key value is never printed, logged, or written to any file.

Usage: launcher.py <runner-args...>   (runner = crew_runner.py, same dir)
Deviation logged in RESULTS.md: credential route = founder-provided
CheaperInference gateway (campaign directive 2026-10-23).
"""
import os, sys, urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# /tmp/campaign-venvs/crewai is a symlink to this home-disk venv (512M tmpfs
# cannot hold the dependency tree). Resolve the real path so a /tmp wipe
# (service restart) cannot break the campaign mid-run.
VENV_PY = os.path.expanduser("~/workspace/.campaign-venvs/crewai/bin/python")
RUNNER = os.path.join(HERE, "crew_runner.py")

def fetch_key():
    req = urllib.request.Request("https://api.cheaperinference.com/v1/chat/completions")
    add_surrogate_to_request(req, "custom.cheaperinference",
                             allowed_hosts=["api.cheaperinference.com"])
    auth = req.headers.get("Authorization") or req.headers.get("authorization")
    if not auth:
        # headers may be stored capitalized differently; scan items without printing values
        for k, v in req.header_items():
            if k.lower() == "authorization":
                auth = v
                break
    if not auth:
        raise RuntimeError("no Authorization header produced by surrogate flow")
    return auth[len("Bearer "):] if auth.startswith("Bearer ") else auth

def main():
    key = fetch_key()
    env = dict(os.environ)
    env["OPENAI_API_KEY"] = key
    env["OPENAI_BASE_URL"] = "https://api.cheaperinference.com/v1"
    # Environment fix (logged in RESULTS.md): the VM runtime's NO_PROXY
    # carries bracketed IPv6 entries ([::1], [fd8b:...]) that httpx's
    # URLPattern parser rejects ("Invalid port: ':1]'") when the OpenAI
    # client builds proxy mounts. Sanitize to a plain list; the egress
    # proxy vars themselves are kept untouched.
    env["NO_PROXY"] = "localhost,127.0.0.1"
    env["no_proxy"] = "localhost,127.0.0.1"
    env["CREWAI_TELEMETRY_OPT_OUT"] = "true"
    env["OTEL_SDK_DISABLED"] = "true"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = [VENV_PY, RUNNER] + sys.argv[1:]
    os.execve(VENV_PY, argv, env)

if __name__ == "__main__":
    main()
