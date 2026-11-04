#!/usr/bin/env bash
# tools/setup_harness.sh — FinePrint harness setup skeleton (see SETUP.md).
#
# Usage:
#   tools/setup_harness.sh check            # report-only: tools, binaries,
#                                           # versions, env presence BY NAME
#                                           # ONLY (never prints a value)
#   tools/setup_harness.sh restore-codex    # the one fully-verified install:
#                                           # pinned codex-cli 0.149.0 via npm,
#                                           # SHA-256-checked before install
#   tools/setup_harness.sh status <harness> # per-harness readiness; pending
#                                           # harnesses print their gap and
#                                           # exit 2 rather than guessing
#
# This skeleton deliberately does NOT install any harness whose install
# path is not verified in SETUP.md. A "pending" harness prints what is
# missing; it never improvises an install command.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_BIN="$REPO/tools/vendor/codex/0.149.0/bin/codex"
CODEX_SHA="bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827"

have() { command -v "$1" >/dev/null 2>&1; }
env_present() { # name only, never the value
  if [ -n "${!1:-}" ]; then echo "set"; else echo "unset"; fi
}

cmd_check() {
  echo "== tools =="
  for t in python3 git node npm; do
    if have "$t"; then echo "  $t: $($t --version 2>&1 | head -1)"; else echo "  $t: MISSING"; fi
  done
  if python3 -m pytest --version >/dev/null 2>&1; then echo "  pytest: present"; else echo "  pytest: MISSING (python3 -m pip install pytest)"; fi
  echo "== pinned oracle (codex 0.149.0) =="
  if [ -f "$CODEX_BIN" ]; then
    if echo "$CODEX_SHA  $CODEX_BIN" | sha256sum -c - >/dev/null 2>&1; then
      echo "  vendored binary: present, sha256 matches pin"
    else
      echo "  vendored binary: PRESENT BUT HASH-MISMATCHED (fail-closed; re-run restore-codex)"
    fi
  else
    echo "  vendored binary: absent (run: tools/setup_harness.sh restore-codex)"
  fi
  echo "== env presence (names only) =="
  for v in NEBIUS_API_KEY GEMINI_API_KEY CURSOR_API_KEY MUSE_HEADLESS_KEY COPILOT_GITHUB_TOKEN; do
    echo "  $v: $(env_present "$v")"
  done
  echo "== harness runners on main =="
  for p in copilot-cli/smoke_runner.py gemini-cli/smoke_runner.py framework/scorecard/copilot-live-v1/runners/series_runner.py framework/scorecard/gemini-live-v1/runners/series_runner.py framework/scorecard/goose-live-v1/runners/matrix.py framework/scorecard/opencode-live-v1/runners/matrix.py framework/scorecard/omnigent-live-v1/runners/matrix.py framework/scorecard/live-agents-v1/runners/proxy.py; do
    if [ -f "$REPO/$p" ]; then echo "  present: $p"; else echo "  MISSING: $p"; fi
  done
  for p in cursor/smoke_runner.py musecode-smoke/install.sh musecode-smoke/smoke_runner.py opencode/install.sh opencode/runner.py; do
    if [ -f "$REPO/$p" ]; then echo "  present: $p"; else echo "  BRANCH-ONLY (not on main): $p"; fi
  done
}

cmd_restore_codex() {
  # Verified recipe (SETUP.md Part A + tools/vendor/codex/0.149.0/VENDORED.md).
  local tmp; tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  cd "$tmp"
  npm pack "@openai/codex@0.149.0-linux-x64"
  mkdir lin && tar -xzf openai-codex-0.149.0-linux-x64.tgz -C lin
  echo "$CODEX_SHA  lin/package/vendor/x86_64-unknown-linux-musl/bin/codex" | sha256sum -c -
  mkdir -p "$(dirname "$CODEX_BIN")"
  cp lin/package/vendor/x86_64-unknown-linux-musl/bin/codex "$CODEX_BIN"
  echo "installed: $CODEX_BIN (sha256 verified)"
}

cmd_status() {
  local h="${1:-}"
  case "$h" in
    codex)
      [ -f "$CODEX_BIN" ] && echo "$CODEX_SHA  $CODEX_BIN" | sha256sum -c - >/dev/null 2>&1 \
        && echo "codex: ready (pinned binary verified)" \
        || echo "codex: NOT READY (run: tools/setup_harness.sh restore-codex)";;
    copilot)
      have copilot && echo "copilot: binary present ($(copilot --version 2>&1 | head -1)); needs COPILOT_GITHUB_TOKEN: $(env_present COPILOT_GITHUB_TOKEN)" \
        || echo "copilot: binary missing (workflow pin: npm install -g @github/copilot@1.0.105)";;
    gemini)
      have gemini && echo "gemini: binary present; needs GEMINI_API_KEY: $(env_present GEMINI_API_KEY)" \
        || echo "gemini: binary missing (workflow pin: npm install -g @google/gemini-cli@0.66.0)";;
    cursor|musecode|opencode-series)
      echo "$h: SETUP CODE PENDING — runner is branch-only, not on main (see SETUP.md Known gaps). Refusing to guess."; exit 2;;
    goose)
      have goose && echo "goose: binary present (package requires 1.57.0 — verify with: goose --version)" \
        || echo "goose: SETUP CODE PENDING — package requires the Goose 1.57.0 binary but gives no install command."; exit 2;;
    omnigent)
      echo "omnigent: SETUP CODE PENDING — runners published, install + re-run docs not in the package README."; exit 2;;
    live-agents)
      echo "live-agents: runners + proxy published; per-agent installs NOT documented in the package. See SETUP.md."; exit 2;;
    pi)
      echo "pi: no in-repo runner (survey row; fix lives on a fork branch)."; exit 2;;
    *)
      echo "usage: tools/setup_harness.sh status <codex|copilot|gemini|cursor|musecode|opencode-series|goose|omnigent|live-agents|pi>" >&2; exit 2;;
  esac
}

case "${1:-}" in
  check) cmd_check;;
  restore-codex) cmd_restore_codex;;
  status) cmd_status "${2:-}";;
  *) echo "usage: tools/setup_harness.sh <check|restore-codex|status <harness>>" >&2; exit 2;;
esac
