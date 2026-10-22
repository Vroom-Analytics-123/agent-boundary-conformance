#!/usr/bin/env python3
"""Pinned-oracle resolution for the Agent Boundary Conformance tooling.

The pinned native oracle is codex-cli 0.149.0. This module resolves the
oracle binary for every tool in this directory:

1. Prefer the sha256-verified vendored copy at
   tools/vendor/codex/0.149.0/bin/codex (see its VENDORED.md).
2. Fall back to the host path /opt/hatch-image/bin/codex.

Every resolution VERIFIES sha256 == the pinned hash and raises (fail closed)
on mismatch. NO oracle work may run on a binary that does not match the pin.

Added Day 5 (2026-10-21): binary-vendoring step of the pin checklist, after
the environment replaced the pinned binary with 0.164.0-alpha.9 on Day 4.
Stdlib only.
"""

from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PINNED_CODEX_VERSION = "0.149.0"
PINNED_CODEX_SHA256 = (
    "bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827"
)
VENDORED_CODEX = REPO / "tools" / "vendor" / "codex" / PINNED_CODEX_VERSION / "bin" / "codex"
HOST_CODEX = Path("/opt/hatch-image/bin/codex")


def sha256_file(p: Path) -> str:
    h = sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def codex_binary() -> Path:
    """Resolve the pinned oracle binary, verifying its sha256 (fail closed)."""
    for candidate in (VENDORED_CODEX, HOST_CODEX):
        if candidate.exists():
            if sha256_file(candidate) != PINNED_CODEX_SHA256:
                raise RuntimeError(
                    f"pinned-oracle mismatch: {candidate} sha256 != "
                    f"{PINNED_CODEX_SHA256}; refusing to run oracle work on an "
                    "unpinned binary"
                )
            return candidate
    raise RuntimeError(
        "no pinned oracle available: neither "
        f"{VENDORED_CODEX} nor {HOST_CODEX} exists"
    )
