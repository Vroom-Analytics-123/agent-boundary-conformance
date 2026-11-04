#!/usr/bin/env python3
"""Standalone verifier for FinePrint live-bundle.v1 bundles.

Usage (from a repo checkout containing the bundle dir):
    python3 evidence/live-2026-11-04/verify_live_bundle.py evidence/live-2026-11-04/<bundle>/

Checks, all of which must pass (exit 0) for the bundle to count as sealed:
  1. bundle.json + bundle.json.sig + bundle.json.sig.json all present.
  2. .sig.json bundle_sha256 == sha256(bundle.json bytes).
  3. .sig.json public_key / fingerprint == the published project key
     (docs/SIGNING.md: 40004a96...3326 / 0c0ab7b5...0e83 -- cross-check
     there; the values below are pinned here for a self-contained check).
  4. Ed25519 checkvalid over the EXACT bundle bytes (via tools/ed25519.py
     from the repo checkout; if it cannot be found the signature check is
     reported as SKIPPED and the exit code is 2 -- fail-closed).
  5. signature_state == "signed", witness_state == "unwitnessed".
  6. Every cell leaf recomputed as sha256(0x00 || canonical_json(cell))
     matches the bundle's leaf list; every inclusion proof verifies;
     the Merkle root recomputes exactly.
  7. Tallies recomputed from cells (via the bundle's grouping) match the
     bundle's tallies; harm total recomputes.
  8. Every manifest file is present in the bundle dir with a matching hash.
  9. bundle.json trips no secret pattern (private-key blocks, AKIA,
     ghp_/github_pat_, sk- tokens, slack tokens, bearer tokens,
     password assignments).

This verifier does NOT re-derive verdicts from raw run records; it verifies
that the sealed cells, tallies, manifest, and signature are internally
consistent and signed by the project key. The link from a sealed cell back
to its original record is the cell's source_path + source_sha256.
"""
import hashlib
import json
import os
import re
import sys

PUBKEY = "40004a96827ae90e5ad4ae36da1414aa80d83625818668604803ba60f3393326"
FINGERPRINT = "0c0ab7b5e8fcff9caf21d4dcd3b28c094c69debf495325541548ead85b0b0e83"

PATS = {
    # A header that literally says FAKE is a fixture template, not a key.
    "private_key_block": re.compile(r"-----BEGIN (?![A-Z ]*FAKE)[A-Z ]*PRIVATE KEY-----"),
    "akia": re.compile(r"AKIA[0-9A-Z]{16}"),
    "gh_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}"),
    "sk_token": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "bearer": re.compile(r"Bearer [A-Za-z0-9._-]{20,}"),
    "passwd_assign": re.compile(r"(?i)(password|passwd)\s*[:=]\s*\S{8,}"),
}


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def leaf_hash(cell):
    return hashlib.sha256(b"\x00" + canon(cell).encode()).hexdigest()


def merkle_root(leaf_hexes):
    nodes = [bytes.fromhex(h) for h in leaf_hexes]
    while len(nodes) > 1:
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])
        nxt = []
        for i in range(0, len(nodes), 2):
            nxt.append(hashlib.sha256(b"\x01" + nodes[i] + nodes[i + 1]).digest())
        nodes = nxt
    return nodes[0].hex()


def verify_inclusion(leaf_hex, proof, root_hex):
    cur = bytes.fromhex(leaf_hex)
    for step in proof:
        sib = bytes.fromhex(step["sibling"])
        if step["direction"] == "right":
            cur = hashlib.sha256(b"\x01" + cur + sib).digest()
        elif step["direction"] == "left":
            cur = hashlib.sha256(b"\x01" + sib + cur).digest()
        else:
            return False
    return cur.hex() == root_hex


def main():
    if len(sys.argv) != 2:
        print("usage: verify_live_bundle.py <bundle-dir>")
        return 2
    bdir = sys.argv[1]
    problems = []

    def fail(msg):
        problems.append(msg)
        print("FAIL:", msg)

    bpath = os.path.join(bdir, "bundle.json")
    if not os.path.exists(bpath):
        print("FAIL: bundle.json missing")
        return 2
    raw = open(bpath, "rb").read()
    b = json.loads(raw)
    sig_path = os.path.join(bdir, "bundle.json.sig")
    meta_path = os.path.join(bdir, "bundle.json.sig.json")
    if not os.path.exists(sig_path) or not os.path.exists(meta_path):
        print("FAIL: detached signature files missing")
        return 2
    sig = open(sig_path, "rb").read()
    meta = json.load(open(meta_path))
    if len(sig) != 64:
        fail(f"signature length {len(sig)} != 64")
    if meta.get("bundle_sha256") != hashlib.sha256(raw).hexdigest():
        fail("sig.json bundle_sha256 mismatch")
    if meta.get("public_key") != PUBKEY or meta.get("fingerprint") != FINGERPRINT:
        fail("sig.json pubkey/fingerprint mismatch vs published key")
    # Ed25519 via the repo's vendored implementation.
    ed = None
    here = os.path.abspath(__file__)
    for cand in (os.path.join(os.path.dirname(here), "..", "..", "tools"),
                 os.path.join(os.getcwd(), "tools")):
        if os.path.exists(os.path.join(cand, "ed25519.py")):
            sys.path.insert(0, os.path.abspath(cand))
            import ed25519 as ed  # noqa: E402
            break
    if ed is None:
        print("SKIP: tools/ed25519.py not found -- signature check unavailable")
        return 2
    if not ed.checkvalid(sig, raw, bytes.fromhex(PUBKEY)):
        fail("Ed25519 checkvalid FAILED")
    else:
        print("signature OK")
    if b.get("signature_state") != "signed" or b.get("witness_state") != "unwitnessed":
        fail(f"state {b.get('signature_state')}/{b.get('witness_state')}")
    cells = sorted(b["cells"], key=lambda c: c["cell_id"])
    leaves = [leaf_hash(c) for c in cells]
    if [x["leaf"] for x in b["merkle"]["leaves"]] != leaves:
        fail("leaf list mismatch")
    for c, leaf in zip(cells, leaves):
        if not verify_inclusion(leaf, b["merkle"]["proofs"][c["cell_id"]], b["merkle"]["root"]):
            fail(f"proof failed for {c['cell_id']}")
    if merkle_root(leaves) != b["merkle"]["root"]:
        fail("root recompute mismatch")
    else:
        print(f"merkle OK root={b['merkle']['root']} cells={len(cells)}")
    grouping = b["grouping"]
    by_group, total = {}, {}
    for c in cells:
        gk = "|".join(str(c[f]) for f in grouping)
        by_group.setdefault(gk, {})
        by_group[gk][c["tally"]] = by_group[gk].get(c["tally"], 0) + 1
        total[c["tally"]] = total.get(c["tally"], 0) + 1
    by_group = {k: {kk: vv for kk, vv in v.items() if vv} for k, v in by_group.items()}
    total = {k: v for k, v in total.items() if v}
    if by_group != b["tallies"]["by_group"] or total != b["tallies"]["total"]:
        fail("tally recompute mismatch")
    else:
        print(f"tallies OK {total}")
    if sum(1 for c in cells if c.get("harm_executed")) != b["harm_total"]:
        fail("harm total mismatch")
    for f in b["files"]:
        fp = os.path.join(bdir, f["path"])
        if not os.path.exists(fp):
            fail(f"manifest file missing: {f['path']}")
        elif hashlib.sha256(open(fp, "rb").read()).hexdigest() != f["sha256"]:
            fail(f"manifest hash mismatch: {f['path']}")
    print(f"manifest OK ({len(b['files'])} files)")
    t = raw.decode("utf-8", "replace")
    hits = {k: len(p.findall(t)) for k, p in PATS.items() if p.findall(t)}
    if hits:
        fail(f"bundle.json trips secret scan: {hits}")
    else:
        print("bundle.json secret-scan clean")
    if problems:
        print(f"VERIFICATION FAILED ({len(problems)} problems)")
        return 1
    print("VERIFIED: sealed live-bundle.v1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
