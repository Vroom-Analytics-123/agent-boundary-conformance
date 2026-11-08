#!/usr/bin/env python3
"""FinePrint free WALL: process-boundary enforcement for the free gate.

The tripwire (fineprint_gate.py) is a fast argv pre-check. The wall is
the enforcement: the agent runs inside a sandbox built from the OS
`unshare` primitive (util-linux) — a new user + mount namespace, plus
a new network namespace in confine mode when no hosts are allowlisted.

Two modes (the policy's "mode", default "deny"):
  - "deny" (the default, antivirus for agents): the protective
    denylist from the signed definitions (tools/fineprint_definitions.py)
    is enforced — the protected targets (SSH keys, .env, tokens, the
    records file) are hidden inside the wall, and the proxy forwards
    everything except denied hosts. Normal work anywhere is allowed.
  - "confine" (opt-in, --confine): the folder allowlist — inside the
    wall the agent can only see the allowed scope (compute_hidden);
    everything else does not exist from its perspective. Egress goes
    through a localhost allowlist proxy when hosts are allowlisted,
    or nowhere at all (--net) when they are not. The denylist still
    applies on top, for protected targets inside the scope.

Mechanism (small, auditable — read this file, it is ~400 lines):
  - Filesystem: the parent computes the boundary — the denylisted
    targets (compute_denied_hidden) and, in confine mode, everything
    outside the allowed scope (compute_hidden). Each is covered
    inside the namespace (empty tmpfs over directories, /dev/null
    over files). The inner setup runs as root inside the user
    namespace, mounts the covers, then drops CAP_SYS_ADMIN
    (setpriv/capsh) before execing the agent, so the agent cannot
    unmount the covers.
  - Network: in confine mode, no hosts allowlisted -> `unshare --net`
    (no route at all); hosts allowlisted -> a localhost allowlist
    proxy (AllowlistProxy) that only forwards allowlisted hosts. In
    deny mode the network is shared and the proxy (denylist mode)
    only runs when hosts are denied, forwarding everything except
    them; the child's proxy env vars point at it.
  - Audit: WALL_START (boundary + tool + egress mode + definitions
    version) and WALL_END (exit code) go to the same hash-chained
    JSONL log as the tripwire; proxy denials are logged with the host
    and the rule. `gate verify-log` checks the chain.

What the wall is NOT (read docs/FREE_GATE.md before trusting it):
  - It enforces SCOPE (paths and hosts), not intent. An agent that
    misuses a file INSIDE the allowed scope is out of scope for the
    wall; that is Check's job (Catalogue v1).
  - It does not isolate the process table: the agent can see host
    process listings in /proc (it cannot ptrace or signal them — that
    needs a capability in the host user namespace, which it does not
    have). The hardened gate adds a pid namespace.
  - The proxy controls egress for tools that honor proxy env vars
    (curl, Python, Node, most CLIs). A process that ignores those
    vars and opens a direct socket can still reach the network when
    the network is shared (deny mode, or confine mode with hosts
    allowlisted). With NO hosts allowlisted in confine mode there is
    no network at all (--net), so there is nothing to bypass.
  - The agent runs as root inside the user namespace. The covers are
    protected by dropping CAP_SYS_ADMIN before exec; if neither
    setpriv nor capsh is available the drop is skipped and a warning
    is printed (the unmount bypass is then open — see FREE_GATE.md).

Do NOT write your own sandbox: this module only assembles OS
primitives (unshare, mount, setpriv/capsh, a stdlib proxy). If
`unshare` is not on PATH, run_walled raises WallUnavailable and the
gate refuses to run — it never silently falls back to the tripwire.

Stdlib only. The inner setup runs as `python3 fineprint_wall.py
--inner -- CMD...` inside the new namespaces.
"""

import fnmatch
import http.client
import http.server
import json
import os
import select
import shutil
import socket
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

# Directories the system needs to run anything. They stay visible
# (read-only in practice for the agent's purposes); everything else
# outside the allowed scope is covered.
SYSTEM_DIRS = ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc",
               "/proc", "/dev", "/sys")

# Exit code for "the wall itself failed to set up" (distinct from the
# agent's own exit code, so a setup failure is recognizable).
EXIT_WALL_SETUP_FAILED = 125


class WallUnavailable(Exception):
    """The wall cannot run here (missing tool, bad policy). Clear,
    actionable — the gate turns this into exit 3 and never runs the
    command unprotected."""


def find_sandbox_tool(path=None):
    """The OS sandbox primitive. `unshare` (util-linux) is present on
    Linux by default, including GitHub ubuntu runners — no install
    step. bwrap is NOT required and NOT used."""
    return shutil.which("unshare", path=path)


def compute_hidden(allowed):
    """The filesystem boundary, as (path, is_dir) pairs to cover.

    `allowed` is a list of absolute directory paths (realpaths). Every
    directory and regular file that is NOT under an allowed path and
    NOT a system directory is hidden: the walk keeps each allowed
    path's ancestor chain visible and covers everything else at each
    level (so siblings of the scope disappear, not just top-level
    directories). Symlinks, sockets, fifos and devices are left alone:
    following one can only reach something already visible (allowed
    or system) or something covered (then it dangles)."""
    allowed = [Path(os.path.realpath(p)) for p in allowed]
    if any(str(p) == "/" for p in allowed):
        return []
    keep = set()
    for p in allowed:
        for i in range(1, len(p.parts) + 1):
            keep.add(Path(*p.parts[:i]))
    keep.update(Path(d) for d in SYSTEM_DIRS)
    hidden = {}
    for d in sorted(keep):
        if not any(str(p).startswith(str(d).rstrip(os.sep) + os.sep)
                   for p in allowed):
            continue  # d is not a proper ancestor of any allowed path
        if not d.is_dir():
            continue
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            ep = Path(e.path)
            if ep in keep:
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    hidden[str(ep)] = True
                elif e.is_file(follow_symlinks=False):
                    hidden[str(ep)] = False
            except OSError:
                continue
    return sorted((Path(p), is_dir) for p, is_dir in hidden.items())


# Directories the denylist walk never descends into: dependency
# trees and caches, where thousands of files live and no user secret
# belongs (a .env inside node_modules is not a user secret). This
# keeps the walk to seconds instead of minutes.
DENYLIST_SKIP_DIRS = frozenset({
    "node_modules", "site-packages", "dist-packages", ".git",
    "__pycache__", ".venv", "venv", ".tox", ".cache",
})

# Where the denylist walk looks, by default: the working directory
# (the project, where .env and records.txt live) plus /tmp and
# /var/tmp (temp secrets). It does NOT walk the whole home directory
# — that found ~3,000 fixture files (records.txt, test keys, .env in
# other projects) and made every gate run mount ~3,000 covers (~10s).
# The user's credentials are covered separately (see
# home_credential_paths): the well-known locations in $HOME and
# /root, checked directly, not walked. A protected file in another
# project directory is therefore NOT hidden unless it is under the
# working directory or /tmp — that bound is documented in
# docs/FREE_GATE.md.
DENYLIST_ROOTS = ("/tmp", "/var/tmp")


def home_credential_paths(rules):
    """The well-known credential locations in $HOME and /root, checked
    directly (one level, no walk): ~/.ssh, ~/.aws, ~/.env,
    ~/.git-credentials, id_rsa*, id_ed25519*. Returns the ones that
    exist and match a denylist rule."""
    import fineprint_definitions as D
    found = []
    for base in (Path.home(), Path("/root")):
        try:
            entries = list(os.scandir(base))
        except OSError:
            continue
        for e in entries:
            if not _basename_might_match(e.name):
                continue
            if D.path_rule(e.path, rules):
                found.append(Path(e.path))
    return found


def _basename_might_match(name):
    """Cheap pre-filter for the denylist walk: fnmatch against every
    pattern for every file is ~10x slower than the walk itself, so
    only run the full match when the basename could possibly match
    a rule. (The full fnmatch still decides; this only skips the
    calls that cannot match.)"""
    if name in (".ssh", ".aws", ".env", ".git-credentials",
                "records.txt", "health"):
        return True
    if name.startswith(("id_rsa", "id_ed25519")):
        return True
    if name.endswith(".pem") and ("key" in name or "private" in name):
        return True
    return False


def compute_denied_hidden(rules, extra_globs=(), roots=None):
    """The denylist boundary, as (path, is_dir) pairs to cover.

    Walks the given roots (default: the working directory plus
    /home, /root, /tmp, /var/tmp) and covers every directory or file
    whose path matches a denylist path rule (or an extra glob from
    the policy). A matching directory is covered whole and not
    descended into. Symlinks are not followed, and dependency trees
    / caches (node_modules, site-packages, .git, venvs, .cache) are
    never descended into. Normal files are never covered."""
    import fineprint_definitions as D
    patterns = []
    for rule in rules:
        if rule.get("kind") == "path":
            patterns.extend(rule.get("patterns", []))
    patterns.extend(extra_globs)
    if not patterns:
        return []
    if roots is None:
        roots = ([Path.cwd()] + [Path(r) for r in DENYLIST_ROOTS]
                 + home_credential_paths(rules))
    # Dedupe: drop a root that is under another root.
    roots = sorted({Path(os.path.realpath(r)) for r in roots
                    if os.path.isdir(r)}, key=lambda p: len(p.parts))
    kept = []
    for r in roots:
        if any(str(r) == str(k) or
               str(r).startswith(str(k).rstrip(os.sep) + os.sep)
               for k in kept):
            continue
        kept.append(r)
    hidden = {}
    # The stack holds os.DirEntry objects: e.is_dir() is cached from
    # the readdir, so the walk does no extra stat per node (a Path
    # walk cost ~10x more here: 275k stats).
    stack = []
    for r in kept:
        if _basename_might_match(r.name) or extra_globs:
            if D.path_rule(str(r), rules) or \
                    any(fnmatch.fnmatch(str(r), g) for g in extra_globs):
                hidden[str(r)] = True
                continue
        try:
            stack.extend(os.scandir(r))
        except OSError:
            continue
    while stack:
        e = stack.pop()
        if e.is_symlink():
            continue
        try:
            is_dir = e.is_dir(follow_symlinks=False)
        except OSError:
            continue
        # Fast pre-filter first; the full fnmatch only for basenames
        # that could match (or when the policy adds extra globs).
        if _basename_might_match(e.name) or extra_globs:
            if D.path_rule(e.path, rules) or \
                    any(fnmatch.fnmatch(e.path, g) for g in extra_globs):
                hidden[e.path] = is_dir
                continue  # covered whole; do not descend
        if not is_dir:
            continue
        if e.name in DENYLIST_SKIP_DIRS:
            continue
        try:
            stack.extend(os.scandir(e.path))
        except OSError:
            continue
    return sorted((Path(p), is_dir) for p, is_dir in hidden.items())


def _path_is_hidden(path, hidden):
    """Is `path` covered by the hidden list (equal to a hidden file,
    or under a hidden directory)?"""
    path = os.path.realpath(path)
    for hp, is_dir in hidden:
        hp = str(hp)
        if is_dir and (path == hp or
                       path.startswith(hp.rstrip(os.sep) + os.sep)):
            return True
        if not is_dir and path == hp:
            return True
    return False


def _is_visible(path, allowed):
    """Is `path` reachable inside the wall (under an allowed path or a
    system directory)?"""
    real = os.path.realpath(path)
    for base in list(allowed) + list(SYSTEM_DIRS):
        if real == base or real.startswith(base.rstrip(os.sep) + os.sep):
            return True
    return False


class AllowlistProxy:
    """A localhost proxy. Two modes:

    - "allowlist" (confine mode): only forwards allowlisted hosts.
    - "denylist" (deny mode): forwards everything EXCEPT denied
      hosts (the `denied` dict maps host -> rule id).

    CONNECT (HTTPS) and absolute-form HTTP requests are checked.
    Anything denied gets a 403 and a WALL_PROXY_DENY entry in the
    audit log (with the rule). The proxy connects directly to the
    target — it does not chain through an upstream proxy, so in a
    restricted-egress environment it can only reach hosts reachable
    directly (localhost, and anything the host can reach directly)."""

    def __init__(self, allowed_hosts=(), log=None, mode="allowlist",
                 denied=None):
        self.allowed_hosts = {h.lower() for h in allowed_hosts}
        self.mode = mode
        self.denied = {h.lower(): r for h, r in (denied or {}).items()}
        self.log = log
        self.server = None
        self.thread = None
        self.port = None

    def start(self):
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _deny(self, host):
                body = b"fineprint wall: host denied\n"
                self.send_response(403)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                if proxy.log is not None:
                    import fineprint_gate as G
                    rule = (proxy.denied.get(host, "DENY-HOST")
                            if proxy.mode == "denylist"
                            else "CONFINE-HOST")
                    proxy.log.append(
                        G.Action("network", host),
                        G.Decision(False,
                                   f"host {host} denied by wall proxy",
                                   rule=rule),
                        note="wall proxy deny", event="WALL_PROXY_DENY")

            def _allowed(self, host):
                host = (host or "").lower()
                if proxy.mode == "denylist":
                    return host not in proxy.denied
                return host in proxy.allowed_hosts

            def do_CONNECT(self):
                hostport = self.path
                host = hostport.rsplit(":", 1)[0].strip("[]").lower()
                if not self._allowed(host):
                    self._deny(host)
                    return
                try:
                    target = socket.create_connection(
                        (host, int(hostport.rsplit(":", 1)[1])), timeout=10)
                except Exception:
                    self.send_error(502, "wall proxy: cannot connect")
                    return
                self.send_response(200, "Connection Established")
                self.end_headers()
                proxy._relay(self.connection, target)
                target.close()

            def _forward_http(self):
                url = urllib.parse.urlsplit(self.path)
                host = (url.hostname or "").lower()
                if not url.hostname:
                    host = (self.headers.get("Host") or "").split(":")[0].lower()
                if not self._allowed(host):
                    self._deny(host)
                    return
                port = url.port or 80
                path = url.path or "/"
                if url.query:
                    path += "?" + url.query
                try:
                    conn = http.client.HTTPConnection(host, port, timeout=10)
                    body = None
                    length = self.headers.get("Content-Length")
                    if length:
                        body = self.rfile.read(int(length))
                    hop = {"connection", "keep-alive", "proxy-authorization",
                           "proxy-connection", "te", "trailer",
                           "transfer-encoding", "upgrade"}
                    headers = {k: v for k, v in self.headers.items()
                               if k.lower() not in hop}
                    conn.request(self.command, path, body=body, headers=headers)
                    resp = conn.getresponse()
                    data = resp.read()
                    self.send_response(resp.status, resp.reason)
                    for k, v in resp.getheaders():
                        if k.lower() not in hop | {"content-length"}:
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    conn.close()
                except Exception:
                    self.send_error(502, "wall proxy: cannot connect")

            do_GET = _forward_http
            do_POST = _forward_http
            do_PUT = _forward_http
            do_DELETE = _forward_http
            do_HEAD = _forward_http
            do_PATCH = _forward_http
            do_OPTIONS = _forward_http

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        return ("127.0.0.1", self.port)

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)

    @staticmethod
    def _relay(a, b):
        """Bidirectional byte relay between two sockets (CONNECT)."""
        a.setblocking(False)
        b.setblocking(False)
        socks = [a, b]
        try:
            while socks:
                r, _, _ = select.select(socks, [], [], 30)
                if not r:
                    break
                for s in r:
                    try:
                        data = s.recv(65536)
                    except OSError:
                        data = b""
                    if not data:
                        socks.remove(s)
                        continue
                    other = b if s is a else a
                    try:
                        other.sendall(data)
                    except OSError:
                        return
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


def _mount(args):
    """Run `mount` (util-linux) with list argv (no shell). Raises on
    failure — a failed cover means the boundary is incomplete, so the
    caller must refuse to run the agent."""
    proc = subprocess.run(["mount"] + args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise WallUnavailable(
            f"wall setup failed: mount {' '.join(args)}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}")


def _inner_main(argv):
    """Runs INSIDE the new namespaces (as root in the user namespace).
    Mounts the covers, drops CAP_SYS_ADMIN, execs the agent. argv is
    the agent command. Exits 125 on setup failure (fail closed)."""
    policy = {}
    policy_file = os.environ.get("FINEPRINT_WALL_POLICY_FILE")
    if policy_file:
        try:
            policy = json.loads(Path(policy_file).read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"wall: bad policy file {policy_file}: {e}",
                  file=sys.stderr)
            return EXIT_WALL_SETUP_FAILED
    else:
        try:
            policy = json.loads(os.environ.get("FINEPRINT_WALL_POLICY",
                                               "{}"))
        except json.JSONDecodeError as e:
            print(f"wall: bad policy in FINEPRINT_WALL_POLICY: {e}",
                  file=sys.stderr)
            return EXIT_WALL_SETUP_FAILED
    hidden = policy.get("hidden", [])
    try:
        _mount(["--make-rprivate", "/"])
        for path, is_dir in hidden:
            if not os.path.lexists(path):
                continue
            if is_dir:
                _mount(["-t", "tmpfs", "tmpfs", path])
            else:
                _mount(["--bind", "/dev/null", path])
    except WallUnavailable as e:
        print(f"wall: {e}", file=sys.stderr)
        return EXIT_WALL_SETUP_FAILED
    # Drop CAP_SYS_ADMIN so the agent cannot unmount the covers (or
    # create new namespaces / mounts). setpriv is util-linux, same
    # package as unshare; capsh is the fallback.
    if shutil.which("setpriv"):
        os.execvp("setpriv",
                  ["setpriv", "--bounding-set=-sys_admin", "--"] + argv)
    if shutil.which("capsh"):
        os.execvp("capsh",
                  ["capsh", "--drop=cap_sys_admin", "--"] + argv)
    print("wall: WARNING: neither setpriv nor capsh is available; the "
          "agent keeps CAP_SYS_ADMIN inside the namespace and could "
          "unmount the cover mounts (see docs/FREE_GATE.md).",
          file=sys.stderr)
    os.execvp(argv[0], argv)
    return EXIT_WALL_SETUP_FAILED  # pragma: no cover


def _denied_hosts_with_rules(policy, rules):
    """{host: rule id} for every host the definitions or the policy
    denies. (In confine mode the allowlist proxy is stricter, so this
    is only used for the denylist proxy and the audit record.)"""
    import fineprint_definitions as D
    denied = {}
    for rule in rules:
        if rule.get("kind") == "host":
            denied[rule.get("match", "").lower()] = rule["id"]
    for host in policy.denied_hosts:
        denied.setdefault(host.lower(), "DENY-HOST")
    return denied


def run_walled(policy, argv, log=None, cwd=None, definitions=None,
               capture_stdout=None, capture_stderr=None):
    """Run `argv` inside the wall. The tripwire pre-flight already ran
    (see fineprint_gate.run_guarded); this is the enforcement. Returns
    the child's exit code. Raises WallUnavailable (clear message) when
    the wall cannot run, and fineprint_definitions.DefinitionsError
    when a definitions pack does not verify — the caller turns both
    into exit 3 and never runs the command unprotected.
    capture_stdout / capture_stderr are file paths the child's
    output is written to (the canary check reads them back); when
    they are None the output is inherited, as before."""
    import fineprint_definitions as D
    import fineprint_gate as G

    tool = find_sandbox_tool()
    if tool is None:
        raise WallUnavailable(
            "the wall needs `unshare` (util-linux) and it is not on "
            "PATH. Install util-linux, or run with --no-wall to use "
            "the tripwire only (not enforced).")
    version, rules, source = (definitions if definitions is not None
                              else D.load_definitions())
    mode = getattr(policy, "mode", "deny")
    cwd = Path(cwd or os.getcwd())
    allowed = [os.path.realpath(p) for p in policy.allowed_paths]
    deny_roots = ([cwd] + [Path(r) for r in DENYLIST_ROOTS]
                  + home_credential_paths(rules))
    denied_hidden = compute_denied_hidden(rules, policy.denied_paths,
                                          roots=deny_roots)
    denied_hosts = _denied_hosts_with_rules(policy, rules)
    if mode == "confine":
        if not any(str(cwd) == p or
                   str(cwd).startswith(p.rstrip(os.sep) + os.sep)
                   for p in allowed):
            raise WallUnavailable(
                f"the wall's allowed scope does not include the working "
                f"directory {cwd}; add it to allowed_paths in "
                f"fineprint-gate.json.")
        for p in allowed:
            if not os.path.isdir(p):
                raise WallUnavailable(
                    f"allowed path {p} does not exist or is not a "
                    f"directory; fix fineprint-gate.json.")
        hidden = compute_hidden(allowed)
        # The denylist still applies inside the scope: hide protected
        # targets that are visible (a target outside the scope is
        # already covered by the scope boundary — covering it again
        # would fail, because its parent directory is already hidden).
        hidden = hidden + [(p, d) for p, d in denied_hidden
                           if _is_visible(str(p), allowed)]
        hosts = sorted({h.lower() for h in policy.allowed_hosts})
    else:
        hidden = denied_hidden
        hosts = sorted(denied_hosts)
    proxy = None
    env = dict(os.environ)
    flags = ["--user", "--map-root-user", "--mount"]
    if mode == "confine":
        if hosts:
            proxy = AllowlistProxy(set(hosts), log=log)
            host, port = proxy.start()
            proxy_url = f"http://{host}:{port}"
            for var in ("http_proxy", "https_proxy", "HTTP_PROXY",
                        "HTTPS_PROXY"):
                env[var] = proxy_url
            # Empty NO_PROXY: localhost targets must go through the
            # proxy too, or a non-allowlisted loopback host would
            # bypass it.
            env["no_proxy"] = env["NO_PROXY"] = ""
            egress = f"proxy (allowlisted hosts: {', '.join(hosts)})"
        else:
            flags.append("--net")
            egress = "none (network namespace, no route)"
    else:
        if denied_hosts:
            proxy = AllowlistProxy(log=log, mode="denylist",
                                   denied=denied_hosts)
            host, port = proxy.start()
            proxy_url = f"http://{host}:{port}"
            for var in ("http_proxy", "https_proxy", "HTTP_PROXY",
                        "HTTPS_PROXY"):
                env[var] = proxy_url
            env["no_proxy"] = env["NO_PROXY"] = ""
            egress = (f"proxy (denied hosts: "
                      f"{', '.join(sorted(denied_hosts))})")
        else:
            egress = "shared (no hosts denied)"
    if log is not None:
        log.append(
            G.Action("wall", "start"),
            G.Decision(True, f"wall up: sandbox unshare, egress {egress}"),
            note="wall start",
            event="WALL_START",
            extra={"sandbox_tool": "unshare",
                   "mode": mode,
                   "definitions": f"v{version} ({source})",
                   "allowed_paths": allowed,
                   "hidden_paths": [str(p) for p, _ in hidden],
                   "allowed_hosts": hosts,
                   "denied_hosts": sorted(denied_hosts),
                   "egress": egress})
    # The inner script is this module. It must be visible inside the
    # wall: in confine mode use it directly when it is under the
    # allowed scope, else copy it into the working directory; in deny
    # mode it is visible unless it is itself a denylisted target.
    module = Path(__file__).resolve()
    cleanup = None
    policy_file = None
    try:
        if mode == "confine":
            visible = _is_visible(str(module), allowed)
        else:
            visible = not _path_is_hidden(str(module), hidden)
        if visible:
            inner_script = str(module)
        else:
            inner_script = str(cwd / f".fineprint-wall-inner-{os.getpid()}.py")
            shutil.copy(module, inner_script)
            cleanup = inner_script
        py = sys.executable
        if mode == "confine":
            if not _is_visible(py, allowed):
                py = "python3"
        elif _path_is_hidden(py, hidden):
            py = "python3"
        # The hidden list is far too long for an env var (a single
        # env value is capped at 128KB — 2,900 targets is ~175KB and
        # exec fails with E2BIG). Write it to a file in the working
        # directory (visible inside the wall) and pass the path.
        policy_file = cwd / f".fineprint-wall-policy-{os.getpid()}.json"
        policy_file.write_text(json.dumps({
            "allowed_paths": allowed,
            "hidden": [[str(p), is_dir] for p, is_dir in hidden]}))
        env["FINEPRINT_WALL_POLICY_FILE"] = str(policy_file)
        unshare_argv = (["unshare"] + flags +
                        [py, inner_script, "--inner", "--"] + list(argv))
        out_f = err_f = None
        try:
            out_f = (open(capture_stdout, "wb")
                     if capture_stdout else None)
            err_f = (open(capture_stderr, "wb")
                     if capture_stderr else None)
            proc = subprocess.run(unshare_argv, cwd=str(cwd), env=env,
                                  stdout=out_f, stderr=err_f)
        except FileNotFoundError as e:
            raise WallUnavailable(f"wall failed to start: {e}")
        finally:
            if out_f is not None:
                out_f.close()
            if err_f is not None:
                err_f.close()
        rc = proc.returncode
    finally:
        if proxy is not None:
            proxy.stop()
        if cleanup is not None:
            try:
                os.unlink(cleanup)
            except OSError:
                pass
        if policy_file is not None:
            try:
                os.unlink(policy_file)
            except OSError:
                pass
    if log is not None:
        log.append(
            G.Action("wall", "end"),
            G.Decision(rc == 0, f"wall down: exit {rc}"),
            note="wall end",
            event="WALL_END",
            extra={"exit_code": rc})
    return rc


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--inner":
        # Everything after "--inner --" is the agent command.
        rest = sys.argv[2:]
        if rest and rest[0] == "--":
            rest = rest[1:]
        if not rest:
            print("wall: --inner needs a command after --", file=sys.stderr)
            sys.exit(EXIT_WALL_SETUP_FAILED)
        sys.exit(_inner_main(rest))
    print(__doc__)
