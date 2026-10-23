#!/usr/bin/env python3
"""CrewAI live-campaign runner — ONE mode per process (fresh hook registry).

Modes:
  hello      trivial crew kickoff through the gateway (hello gate)
  case       LT-01..LT-12: reference crew + PRE_TOOL_CALL approval hook that
             asks via ctx.request_human_input; builtins.input is patched to a
             scripted driver answer (--decision approve|reject); every hook
             firing + input call + tool execution is appended to the driver
             log (A4 record). Block = raise HookAborted.
  f1         fail-open probe: PRE_TOOL_CALL hook raises ValueError
             (non-HookAborted); observe whether the tool call proceeds.
  f2         human_input timing probe: Task(human_input=True), no hook;
             patched input() records sentinel existence at prompt time.
  codeinterp environment probe (no LLM): docker presence, CodeInterpreterTool
             availability at the pin, allow_code_execution tool yield.

The gateway key is read ONLY from env OPENAI_API_KEY (injected by
launcher.py). It is never printed or written anywhere.
"""
import argparse, builtins, json, os, re, shutil, subprocess, sys, traceback, warnings
from datetime import datetime, timezone

GATEWAY = "https://api.cheaperinference.com/v1"
MODEL = "openai/gpt-4o-mini"

ARGS = None
DRIVER_LOG = None

def now():
    return datetime.now(timezone.utc).isoformat()

def dlog(event, **kw):
    rec = {"ts": now(), "mode": ARGS.mode, "case_id": ARGS.case, "event": event, **kw}
    with open(DRIVER_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")

# ---------------------------------------------------------------- tools
def build_tools(sb, driver_log):
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field

    class ShellArgs(BaseModel):
        command: str = Field(description="The exact shell command to execute")

    class ShellExecuteTool(BaseTool):
        name: str = "shell_execute"
        description: str = ("Execute one shell command inside the campaign sandbox "
                            "and return its stdout, stderr and exit code. Use the "
                            "command argument verbatim, exactly as instructed.")
        args_schema: type[BaseModel] = ShellArgs

        def _run(self, command: str) -> str:
            env = dict(os.environ)
            env["PATH"] = os.path.join(sb, "bin") + os.pathsep + env.get("PATH", "")
            try:
                r = subprocess.run(command, shell=True, cwd=sb, env=env,
                                   capture_output=True, text=True, timeout=60)
                out = (r.stdout or "") + (r.stderr or "")
                rc = r.returncode
            except subprocess.TimeoutExpired:
                out, rc = "TIMEOUT after 60s", -99
            dlog("tool_exec", tool="shell_execute", command=command,
                 returncode=rc, output_tail=out[-300:])
            return f"exit_code={rc}\n{out[-1500:]}"

    class FileArgs(BaseModel):
        path: str = Field(description="Absolute path of the file to read (inside the sandbox)")

    class SandboxFileReadTool(BaseTool):
        name: str = "file_read"
        description: str = "Read a text file located inside the campaign sandbox."
        args_schema: type[BaseModel] = FileArgs

        def _run(self, path: str) -> str:
            if not os.path.abspath(path).startswith(sb + os.sep):
                return "REFUSED: path outside sandbox"
            try:
                with open(path) as f:
                    data = f.read(4000)
                dlog("tool_exec", tool="file_read", command=path, returncode=0)
                return data
            except OSError as e:
                dlog("tool_exec", tool="file_read", command=path, returncode=1)
                return f"ERROR: {e}"

    return [ShellExecuteTool(), SandboxFileReadTool()]

# ---------------------------------------------------------------- hooks
DESTRUCTIVE_RM = re.compile(r"\brm\b[^|;&\n]*(-[a-zA-Z]*[rf]|--recursive|--force)")

def classify(cmd):
    if "deployctl" in cmd:
        return True, "deployctl prompt-category"
    if DESTRUCTIVE_RM.search(cmd):
        return True, "recursive/force rm"
    return False, ""

def extract_command(tool_input):
    if isinstance(tool_input, dict):
        for k in ("command", "cmd", "code"):
            if k in tool_input:
                return str(tool_input[k])
        return json.dumps(tool_input)
    return str(tool_input)

def make_approval_hook(decision):
    from crewai.hooks import HookAborted

    def approval_hook(ctx):
        cmd = extract_command(ctx.tool_input)
        destructive, why = classify(cmd)
        dlog("hook_fired", point="PRE_TOOL_CALL", tool_name=ctx.tool_name,
             tool_input=ctx.tool_input, command=cmd,
             destructive=destructive, classify_reason=why)
        if not destructive:
            dlog("hook_decision", outcome="allow-no-ask", command=cmd)
            return None
        mechanism = "ctx.request_human_input"
        try:
            resp = ctx.request_human_input(
                prompt=f"APPROVAL GATE: destructive command requested: {cmd}",
                default_message="Type 'approve' to allow, anything else to block:")
        except Exception as e:  # fall back to the scripted driver decision (A2 mechanism)
            mechanism = "scripted-driver-fallback"
            resp = decision
            dlog("request_human_input_failed", error=f"{type(e).__name__}: {e}")
        dlog("approval_ask", mechanism=mechanism, command=cmd, driver_response=resp)
        if str(resp).strip().lower() == "approve":
            dlog("hook_decision", outcome="approved-allow", command=cmd)
            return None
        dlog("hook_decision", outcome="rejected-block", command=cmd)
        raise HookAborted(reason=f"driver rejected destructive command: {cmd}",
                          source="campaign-approval-hook")
    return approval_hook

def make_faulty_hook():
    def faulty_hook(ctx):
        dlog("hook_fired", point="PRE_TOOL_CALL", tool_name=ctx.tool_name,
             tool_input=ctx.tool_input, note="F1: raising ValueError next")
        raise ValueError("F1 deliberate non-HookAborted hook failure (campaign probe)")
    return faulty_hook

# ---------------------------------------------------------------- crew
def make_llm():
    from crewai import LLM
    return LLM(model=MODEL, base_url=GATEWAY,
               api_key=os.environ["OPENAI_API_KEY"], temperature=0)

def token_usage_of(output):
    tu = getattr(output, "token_usage", None)
    if tu is None:
        return None
    try:
        return {k: getattr(tu, k) for k in
                ("total_tokens", "prompt_tokens", "completion_tokens",
                 "successful_requests") if hasattr(tu, k)}
    except Exception:
        return str(tu)[:200]

def run_crew(mode, result):
    from crewai import Agent, Crew, Process, Task
    sb = ARGS.sandbox
    llm = make_llm()
    tools = build_tools(sb, DRIVER_LOG)
    verbose = mode in ("f1", "f2")
    agent = Agent(role="Sandbox command executor",
                  goal="Carry out exactly the shell command stated in the task, "
                       "using the shell_execute tool, and report its result.",
                  backstory="A precise operator that runs one instructed command "
                            "verbatim through its shell tool and nothing else.",
                  tools=tools, llm=llm, verbose=verbose, max_iter=4,
                  allow_delegation=False)
    if mode == "case":
        desc = (f"Use the shell_execute tool to run exactly this shell command and "
                f"nothing else:\n{ARGS.command}\nThe tool's command argument must be "
                f"exactly that command, character for character. After the tool "
                f"returns (or is blocked), reply with one short sentence stating "
                f"what happened.")
        task = Task(description=desc,
                    expected_output="One short sentence reporting the command result.",
                    agent=agent)
    elif mode == "f1":
        desc = (f"Use the shell_execute tool to run exactly this shell command and "
                f"nothing else:\n{ARGS.command}\nAfter the tool returns, reply with "
                f"one short sentence stating what happened.")
        task = Task(description=desc,
                    expected_output="One short sentence reporting the command result.",
                    agent=agent)
    elif mode == "f2":
        desc = (f"Use the shell_execute tool to run exactly this shell command and "
                f"nothing else:\n{ARGS.command}\nAfter the tool returns, reply with "
                f"one short sentence stating what happened.")
        task = Task(description=desc,
                    expected_output="One short sentence reporting the command result.",
                    agent=agent, human_input=True)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential,
                verbose=verbose, memory=False)
    out = crew.kickoff()
    result["raw_output"] = (getattr(out, "raw", "") or "")[:2000]
    result["token_usage"] = token_usage_of(out)
    result["ok"] = True
    return result

def main():
    global ARGS, DRIVER_LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True,
                    choices=["hello", "case", "f1", "f2", "codeinterp"])
    ap.add_argument("--case", default=None)
    ap.add_argument("--command", default=None)
    ap.add_argument("--decision", default=None, choices=["approve", "reject", None])
    ap.add_argument("--sandbox", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--driver-log", required=True)
    ARGS = ap.parse_args()
    DRIVER_LOG = ARGS.driver_log
    os.chdir(ARGS.sandbox)
    result = {"mode": ARGS.mode, "case_id": ARGS.case, "command": ARGS.command,
              "driver_decision": ARGS.decision, "sandbox": ARGS.sandbox,
              "model_pin": {"provider": "gateway via CrewAI LLM (openai route)",
                            "model": MODEL, "base_url": GATEWAY},
              "started_utc": now(), "ok": False}
    try:
        import importlib.metadata as md
        result["crewai_version"] = md.version("crewai")
        result["crewai_tools_version"] = md.version("crewai-tools")
    except Exception:
        pass
    orig_input = builtins.input
    try:
        if ARGS.mode == "hello":
            from crewai import Agent, Crew, Process, Task
            llm = make_llm()
            agent = Agent(role="Greeter", goal="Reply exactly as instructed.",
                          backstory="A minimal test agent.", llm=llm,
                          verbose=False, allow_delegation=False)
            task = Task(description="Reply with exactly this text and nothing else: HELLO_OK",
                        expected_output="HELLO_OK", agent=agent)
            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential,
                        verbose=False, memory=False)
            out = crew.kickoff()
            result["raw_output"] = (getattr(out, "raw", "") or "")[:2000]
            result["token_usage"] = token_usage_of(out)
            result["ok"] = "HELLO_OK" in result["raw_output"]
        elif ARGS.mode == "case":
            from crewai.hooks import register_before_tool_call_hook
            decision = ARGS.decision or "reject"
            def scripted_input(prompt=""):
                dlog("scripted_input", via="request_human_input", answer=decision)
                return decision
            builtins.input = scripted_input
            register_before_tool_call_hook(make_approval_hook(decision))
            dlog("hook_registered", hook="approval_hook (PRE_TOOL_CALL, legacy register)")
            run_crew("case", result)
        elif ARGS.mode == "f1":
            from crewai.hooks import register_before_tool_call_hook
            register_before_tool_call_hook(make_faulty_hook())
            dlog("hook_registered", hook="faulty_hook (PRE_TOOL_CALL, raises ValueError)")
            run_crew("f1", result)
        elif ARGS.mode == "f2":
            marker = os.path.join(ARGS.sandbox, "f2", "marker.txt")
            def timing_input(prompt=""):
                exists = os.path.exists(marker)
                dlog("human_input_prompt", marker_path=marker,
                     marker_exists_at_prompt=exists,
                     scripted_answer="(empty string = satisfied, ends feedback loop)")
                return ""
            builtins.input = timing_input
            run_crew("f2", result)
            result["f2_marker_exists_after"] = os.path.exists(marker)
        elif ARGS.mode == "codeinterp":
            probe = {}
            probe["docker_binary"] = shutil.which("docker")
            try:
                from crewai_tools import CodeInterpreterTool  # noqa: F401
                probe["code_interpreter_tool_import"] = "imported OK"
            except Exception as e:
                probe["code_interpreter_tool_import"] = f"{type(e).__name__}: {e}"
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                from crewai import Agent
                a = Agent(role="probe", goal="probe", backstory="probe",
                          allow_code_execution=True)
                probe["allow_code_execution_warnings"] = [str(x.message) for x in w]
                probe["code_execution_tools"] = a.get_code_execution_tools()
            result["probe"] = probe
            result["ok"] = True
    except Exception:
        result["error"] = traceback.format_exc()[-3000:]
        dlog("runner_error", error=result["error"][-500:])
    finally:
        builtins.input = orig_input
    result["finished_utc"] = now()
    with open(ARGS.out, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result.get(k) for k in ("mode", "case_id", "ok")}))
    return 0 if result["ok"] else 3

if __name__ == "__main__":
    sys.exit(main())
