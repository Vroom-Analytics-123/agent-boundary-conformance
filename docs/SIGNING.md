# Bundle signing (Ed25519)

**Status:** implemented 2026-10-22 (grant-strengthening pack). New bundles built
with `tools/build_evidence_bundle.py --sign` (or `build_protected_bundle.py
--sign`) get `signature_state="signed"`. `witness_state` stays `"unwitnessed"` —
signing is an authorship/integrity attestation, not independent witnessing.

## Project public key (published)

| Field | Value |
|---|---|
| Algorithm | Ed25519 (RFC 8032) |
| Public key (hex) | `40004a96827ae90e5ad4ae36da1414aa80d83625818668604803ba60f3393326` |
| Fingerprint (SHA256 of the raw 32-byte public key, hex) | `0c0ab7b5e8fcff9caf21d4dcd3b28c094c69debf495325541548ead85b0b0e83` |
| Key generated | 2026-10-22, `tools/signing.py gen-key` |

Verify any published fingerprint against this document before trusting a
signature.

## Key custody

- The PRIVATE key lives at `~/.fineprint/ed25519.key` (workspace-local, mode
  0600), **outside all repositories**. It is git-ignored by location, never
  printed by any tool, never committed, never transmitted.
- Key path override: `$FINEPRINT_SIGNING_KEY`.
- The implementation is pure Python, stdlib only (`tools/ed25519.py`,
  vendored; correctness pinned by the RFC 8032 §7.1 test vectors in
  `tests/test_signing.py`). No third-party crypto dependency, so the
  replication story stays "python3 and the repo".
- Rotation: a new key means a new public key + fingerprint published here;
  existing signatures remain verifiable with the public key recorded in
  their `.sig.json` metadata.

## What a signature means (and does not)

- **Detached:** the 64 raw signature bytes live in `<bundle>.sig` next to the
  bundle, with metadata in `<bundle>.sig.json` (algorithm, public key,
  fingerprint, `signed_at_utc`, `bundle_sha256`). **Bundle bytes are never
  modified to carry a signature** — sealing stays byte-stable.
- **Scope:** the signature covers the EXACT bytes of the bundle file. Any
  byte change invalidates it.
- `signature_state="signed"` is set **only at build time**, when the key was
  present and the bytes now on disk are the bytes that were signed.
- **Post-seal attestations:** a detached signature added to an already-sealed
  bundle (e.g. the post-fix bundles sealed before signing existed) does NOT
  change that bundle's `signature_state` — it honestly remains `"unsigned"`,
  and the `.sig.json` metadata records the attestation separately. The
  verifier reports these as "detached post-seal attestation".
- A signature says *the project attests these are the bytes it sealed*. It
  says nothing about the correctness of the oracle, the corpus, or the
  invariants — those are established by the hash pins, the pre-registration,
  and the negative controls.

## Verifying

```bash
# full offline verification (Merkle + pins + signature when present)
python3 tools/verify_bundle.py evidence/postfix-2026-10-22/bundle.json

# signature only, against the published public key
python3 tools/signing.py verify-bundle \
  --bundle evidence/postfix-2026-10-22/bundle.json \
  --pubkey 40004a96827ae90e5ad4ae36da1414aa80d83625818668604803ba60f3393326
```

## Signed bundles so far

| Bundle | signature_state | Detached signature |
|---|---|---|
| `evidence/postfix-2026-10-22/bundle.json` (`boundary-day2-20261022T160548Z`, Merkle `5a974fe6…`) | `unsigned` (sealed before signing existed) | `bundle.json.sig` + `bundle.json.sig.json` — post-seal attestation, 2026-10-22 |
| `evidence/postfix-2026-10-22/bundle-protected.json` | `unsigned` (sealed before signing existed) | `bundle-protected.json.sig` + `bundle-protected.json.sig.json` — post-seal attestation, 2026-10-22 |

`--sign` fails closed: if the key is absent at build time, the build errors
rather than silently emitting an unsigned bundle.
