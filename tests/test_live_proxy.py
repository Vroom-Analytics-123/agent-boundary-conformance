#!/usr/bin/env python3
"""Tests for tools/live_proxy.py — proxy lifecycle management and the
vendored per-harness proxies.

Lifecycle tests use a stub HTTP server (no credentials, no network).
Vendored-proxy tests start the actual vendored scripts from the repo
path and hit their health endpoints; they skip when the surrogate
helper (dynamic_credentials) is not importable, because the vendored
proxies import it at module load — that is an environment gap, not a
proxy failure, and the skip says so.

Stdlib only (unittest). Run: python3 tests/test_live_proxy.py
"""

import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import live_proxy as LP  # noqa: E402


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def surrogate_available():
    """True when the vendored proxies' import-time dependency loads.

    The helper lives at a fixed path, not on sys.path, so check the
    file directly (importlib.find_spec with a path list does not do
    what it looks like it does — it returned None here even though
    the module exists).
    """
    return Path(
        "/opt/muse/skills/custom-connector-setup/bin"
        "/dynamic_credentials.py").exists()


class TestTcpHealth(unittest.TestCase):
    def test_closed_port_is_unhealthy(self):
        self.assertFalse(LP.tcp_health(free_port(), timeout=1.0))

    def test_open_port_is_healthy(self):
        port = free_port()
        srv = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            # The server needs a moment to bind; poll, don't race it.
            deadline = time.time() + 10
            healthy = False
            while time.time() < deadline:
                if LP.tcp_health(port, timeout=1.0):
                    healthy = True
                    break
                time.sleep(0.25)
            self.assertTrue(healthy,
                            "http.server did not listen in time")
        finally:
            srv.terminate()
            srv.wait(timeout=10)


class TestProxyLifecycle(unittest.TestCase):
    def test_start_and_stop_stub_server(self):
        port = free_port()
        spec = LP.ProxySpec(
            script=None, command=[sys.executable, "-m", "http.server",
                                  str(port)],
            port=port, health_path="/")
        proc = LP.start_proxy(spec, timeout=15.0)
        try:
            self.assertIsNone(proc.poll())  # still running
            self.assertTrue(LP.http_health(
                f"http://127.0.0.1:{port}/", timeout=2.0))
        finally:
            LP.stop_proxy(proc)
        self.assertIsNotNone(proc.poll())

    def test_start_times_out_when_nothing_listens(self):
        port = free_port()
        spec = LP.ProxySpec(
            script=None,
            command=[sys.executable, "-c",
                     "import time; time.sleep(60)"],
            port=port, health_path=None)
        with self.assertRaises(LP.ProxyError):
            LP.start_proxy(spec, timeout=2.0)

    def test_stop_kills_a_stubborn_process(self):
        port = free_port()
        spec = LP.ProxySpec(
            script=None, command=[sys.executable, "-m", "http.server",
                                  str(port)],
            port=port, health_path="/")
        proc = LP.start_proxy(spec, timeout=15.0)
        LP.stop_proxy(proc, timeout=2.0)
        self.assertIsNotNone(proc.poll())


class TestVendoredProxies(unittest.TestCase):
    """Each vendored proxy must start from its REPO path and answer
    its own health check. Ports: claude is fixed at 8898 by the
    script; gemini/omnigent accept --port so tests use free ports."""

    def setUp(self):
        if not surrogate_available():
            self.skipTest(
                "dynamic_credentials not importable here; vendored "
                "proxies cannot load (environment gap, not a proxy "
                "failure)")

    def _env(self):
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = (
            "/opt/muse/skills/custom-connector-setup/bin"
            + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""))
        return env

    def test_claude_proxy_starts_and_listens(self):
        port = 8898
        if LP.tcp_health(port, timeout=1.0):
            self.skipTest("port 8898 already in use")
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "tools" / "proxies"
                                 / "claude_proxy.py")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=self._env())
        try:
            deadline = time.time() + 20
            while time.time() < deadline:
                if LP.tcp_health(port, timeout=1.0):
                    break
                time.sleep(0.5)
            self.assertTrue(LP.tcp_health(port, timeout=2.0),
                            "claude proxy did not listen on 8898")
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def test_gemini_translator_answers_root(self):
        port = free_port()
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "tools" / "proxies"
                                 / "gemini_translator.py"),
             "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=self._env())
        try:
            # Poll: the translator needs a moment to bind.
            deadline = time.time() + 20
            healthy = False
            while time.time() < deadline:
                if LP.http_health(f"http://127.0.0.1:{port}/",
                                  timeout=2.0):
                    healthy = True
                    break
                time.sleep(0.5)
            self.assertTrue(healthy,
                            "gemini translator did not answer GET /")
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/", timeout=5) as r:
                self.assertEqual(r.status, 200)
                # Verified live: the translator answers {"ok": true,
                # "proxy": "gemini-to-openai"}, not {"status": "ok"}.
                self.assertEqual(json.loads(r.read()),
                                 {"ok": True,
                                  "proxy": "gemini-to-openai"})
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def test_omnigent_proxy_answers_health(self):
        port = free_port()
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "tools" / "proxies"
                                 / "omnigent_proxy.py"),
             "--port", str(port), "--arm", "cheaper",
             "--model", "beam-free"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=self._env())
        try:
            # Poll: the proxy needs a moment to bind.
            deadline = time.time() + 20
            healthy = False
            while time.time() < deadline:
                if LP.http_health(
                        f"http://127.0.0.1:{port}/health", timeout=2.0):
                    healthy = True
                    break
                time.sleep(0.5)
            self.assertTrue(healthy,
                            "omnigent proxy did not answer GET /health")
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=5) as r:
                self.assertEqual(r.status, 200)
                # Verified live: /health answers {"ok": true,
                # "arm_model": <model>}.
                self.assertEqual(json.loads(r.read()),
                                 {"ok": True, "arm_model": "beam-free"})
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
