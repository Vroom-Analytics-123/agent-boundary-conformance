#!/bin/sh
# Pinned OpenCode install for the harness-opencode workflow.
# Installs opencode-ai@1.19.5 (the v1 line) and FAILS unless
# `opencode --version` reports exactly 1.19.5. On runners where the
# meta-package's platform detection fails, falls back to the
# linux-x64 platform package at the same version — the version pin,
# not the package path, is the invariant. Never installs "latest".
set -eu
if opencode --version 2>/dev/null | grep -qx "1.19.5"; then
  echo "opencode 1.19.5 already present"
  exit 0
fi
if ! npm install -g opencode-ai@1.19.5; then
  echo "meta-package install failed; trying platform package"
  npm install -g opencode-linux-x64@1.19.5
fi
VER="$(opencode --version)"
echo "opencode version: $VER"
if [ "$VER" != "1.19.5" ]; then
  echo "VERSION MISMATCH: expected 1.19.5, got $VER" >&2
  exit 1
fi
