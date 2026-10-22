# REPLICATION.md — independent replay of the sealed evidence

One command reproduces the sealed Day-2 evidence bundle from scratch:

```bash
./tools/replicate.sh [sealed-bundle.json]
```

The script fetches the pinned oracle via the committed npm recipe (SHA-256
verified, fail-closed), reruns the corpus, rebuilds the bundle, and compares
Merkle roots against the published expectations **read from the sealed bundle
itself**. It prints a plain verdict:

- `REPLICATION VERDICT: PASS` — fresh Merkle root == sealed Merkle root.
- `REPLICATION VERDICT: DIFF` — inputs on disk differ from the sealed pins
  (named file by file), or the roots differ. A DIFF names the cause; it is
  never silent.
- `ERROR` (exit 2) — tooling or network failure (e.g. the oracle could not be
  fetched). A fetch failure is an ERROR, not a DIFF: replication could not be
  attempted.

Exit codes: 0 = PASS, 1 = DIFF, 2 = ERROR.

The default target is `evidence/day2-2026-10-22/bundle.json`; pass
`evidence/postfix-2026-10-22/bundle.json` to replicate the post-fix seal the
same way. The script never modifies the sealed bundle, the sealed corpus, or
the held-out split. It writes one rerun record under `evidence/reruns/` (repo
convention) and builds the fresh bundle in a throwaway dir inside the repo
(removed on PASS, kept for inspection on DIFF).

## What the script checks, in order

1. **Published expectations** — Merkle root + pinned input hashes extracted
   from the sealed bundle.
2. **Input drift check** — `fixtures/fixtures.json`, `security/invariants.yaml`
   and every rules file are hashed and compared to the sealed pins. Any drift
   is a DIFF with the exact files named (a sealed root cannot be reproduced
   from different inputs).
3. **Pinned oracle** — the vendored `tools/vendor/codex/0.149.0/bin/codex` is
   SHA-256-verified; if missing or mismatched it is fetched via the committed
   recipe (`npm pack @openai/codex@0.149.0-linux-x64`, hash must equal
   `bbc3341e…672827`) and installed. A fetch failure is an ERROR.
4. **Rerun + rebuild** — `tools/run_fixtures.py`, then
   `tools/build_evidence_bundle.py --out-dir <throwaway>`.
5. **Root comparison** — fresh Merkle root vs sealed Merkle root.

## Self-test record (dated, honest)

**2026-10-22 — PASS.** Run from a pristine worktree at `816b906`
("Day-6: Boundary Scorecard export + CI (PRE-FIX evidence)"):

```
[replicate] all input files match the sealed pins.
[replicate] vendored oracle missing; fetching via the committed recipe.
[replicate] fetching @openai/codex@0.149.0-linux-x64 via npm (this downloads ~100 MB)...
[replicate] fetched binary verified against the pin and installed at .../tools/vendor/codex/0.149.0/bin/codex
[replicate] rerunning the corpus with the pinned oracle...
[replicate] rerun record: .../evidence/reruns/rerun-20261022T181500Z.json
[replicate] rebuilding the bundle (throwaway dir: .../.replication-tmp.vSp35t)...
sealed root: 003bfbb3256032c5febef2559636393d671d75c56ee79788d2d594a38c2d3b32
fresh  root: 003bfbb3256032c5febef2559636393d671d75c56ee79788d2d594a38c2d3b32
[replicate] fresh bundle matched the sealed root; removing throwaway dir ...
REPLICATION VERDICT: PASS
```

The fetch path was exercised end-to-end (the binary is git-ignored, so the
pristine worktree had no oracle): npm tarball → extraction → SHA-256 matched
the pin → installed → 41 fixtures + 4 negative controls rerun → rebuilt
bundle's Merkle root byte-identical to the sealed `003bfbb3…`.

## Known constraints (read before claiming replication)

1. **The tree must match the seal's era.** The Day-2 bundle's pins correspond
   to the pre-dual-verdict-correction tree: `security/invariants.yaml` at
   `aa4fcb9f…` (changed by `ab3cddf`), pre-fix corpus/rules. Verified
   pin-intact commits: `816b906`, `8657e0f`. On the current tree the script
   correctly reports DIFF, naming the drifted inputs (post-fix corpus
   `2dc43a86…`, post-fix rules `9b83f89f…`, dual-verdict invariants
   `9ebcf775…`). The seal commit `fef248b` itself predates the vendoring
   step (`tools/pin.py` did not exist there; the runner hardcoded the host
   binary path) — see constraint 3.
2. **Binary path.** The sealed bundle records
   `binary_path: /opt/hatch-image/bin/codex` — the host path, which the
   environment replaced with an unpinned build on Day 4. The kit does NOT use
   it; per the Day-5 pin discipline it resolves the oracle through
   `tools/pin.py` (vendored SHA-256-verified copy, fail-closed) or fetches it.
   `tools/verify_bundle.py`'s host-path hash check therefore reports the
   Day-2 bundle against the *current* tree; the meaningful verification is
   this kit's, on a pin-intact tree.
3. **Pre-vendoring trees.** Commits before `ad5c24a` (Day-5 vendoring) have no
   `tools/pin.py`; their runner hardcodes the host binary path. The kit's
   oracle resolution applies where `pin.py` exists. Replicating from an older
   tree requires the era-appropriate oracle handling — documented here, not
   silently worked around.
4. **Disk space.** The fetch needs ~350 MB transient space (compressed
   tarball + 258 MB binary); it respects `$TMPDIR` and cleans up on failure.
   (Found the hard way: a 512 MB `/tmp` tmpfs ENOSPC'd the first self-test;
   the script now extracts only the binary, moves instead of copying, and
   fails loudly instead of claiming a partial install.)
5. **Bugs found by self-testing this kit** (fixed 2026-10-22): `set -e`
   silently killed the script before the DIFF branch on drifted inputs
   (restructured to `if`/`else`); a failed `cp` inside an `&&` list did not
   trigger `set -e` and the script claimed a successful install (now explicit
   `mv` + checks); the builder crashed on out-dirs outside the repo (the
   throwaway dir now lives inside the repo and is git-ignored).
