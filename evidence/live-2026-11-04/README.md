# Sealed live bundles — 2026-11-04

Fourteen signed, verifiable bundles covering the completed FinePrint measurement runs.
Branch-only. Nothing here moves a badge, changes a scorecard number, or merges to main:
promotion still needs the owner's explicit word. Sealing attests authorship and
integrity (signature_state "signed", witness_state "unwitnessed" -- signing is not
independent witnessing, per docs/SIGNING.md).

## Bundles

| Bundle | Cells | Merkle root | Tallies |
|---|---|---|---|
| amp-live | 48 | `1b2bea1c72cc4fc00815cfe3fa17aa60f0cc16f67b6dd35c212e03fc2a34eba5` | executed 10, no_decision 2, pass 36 |
| live-agents | 480 | `b1f4c9714042310da0b5ee14b8bb8036a722852de4c08a144ebbcbbbc34349a6` | executed 189, no_decision 117, overblock 16, pass 158 |
| omnigent-live | 96 | `3d7c4c3c83909b67f270221fa46b75178d70b1ebcd3e05f90f42daed243e2b65` | executed 29, no_decision 18, pass 48, timeout 1 |
| goose-live | 72 | `3b49c461229bc0a45cb3cd2afb9596c67cb2ba1a958464bd8a3bc46959edaf0c` | executed 16, no_decision 10, overblock 8, pass 38 |
| opencode-live | 96 | `bbfb0edb82f91bfc4c1e5ab30f5f380837c4de7aa09e30c59474257ddbb72b76` | executed 23, no_decision 25, overblock 8, pass 40 |
| musecode-n3-rerun | 39 | `291be9bc3e2919746f6a8b4c6c21f05186e425660f6841d05d1ff6e82b88458d` | fail 26, pass 13 |
| copilot-live | 15 | `e157dc966e1d8e2f7b7f5a122aafe5ea363aa4934200de50f14fc443bad95084` | executed 5, pass 10 |
| gemini-live | 14 | `96a32bdff621acc97b7eba38afe08b9734de24cff86246ef83757c40455265f6` | executed 2, no_decision 1, pass 11 |
| adapters-v1 | 120 | `4dd29a9269a6d302d5eba72b5efc7f0219d0508ded8132ded4f9d9e5c0b1c98d` | allow 19, forbidden 10, prompt 34, unknown 57 |
| claudecode-live | 48 | `7993b30e5f0ca7753bd3b1aa366280abf56d5f5468c42e10582599cb43f65cdf` | executed 6, no_decision 13, overblock 2, pass 27 |
| gemini-live-full | 48 | `d841b76ef2efbbd0f03fdb9343f54fc00589df02b22f68a7bc8fc4752bdcf27f` | executed 28, no_decision 3, pass 17 |
| copilot-full | 48 | `6685d7a9aa2e62ff9b3aa47261e36296979a3caa02f5cdee1c124c15813df3c4` | executed 25, no_decision 10, pass 13 |
| codex-live-v1 | 48 | `00a71b7e9eba548dc4923101b3c8905dfb1850fa9546b186edbc0a3a32708f26` | executed 19, no_decision 14, pass 15 |
| musecode-v1 | 48 | `23e92ebc351428223370564d76f72630a726208d8e59f6cd97719ae97603bff7` | executed 4, no_decision 17, overblock 4, pass 23 |

### amp-live

Amp live v1, 48 cells (medium r1+r2). PASS 36 / EXECUTED 10 / NO-DECISION 2.

Bundle dir: `evidence/live-2026-11-04/amp-live/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### live-agents

Live-agents v1, 480 runs (5 agents x 2 arms x 2 repeats). Post V1-23-repair tallies.

Bundle dir: `evidence/live-2026-11-04/live-agents/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### omnigent-live

Omnigent live v1, 96 cells (cheaper + meta arms). PASS 48 / EXECUTED 29 / NO-DECISION 18 / TIMEOUT 1.

Bundle dir: `evidence/live-2026-11-04/omnigent-live/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### goose-live

Goose live v1, 72 cells (default + deny + hardened, r1). Mode-gate caveat applies.

Bundle dir: `evidence/live-2026-11-04/goose-live/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### opencode-live

OpenCode live v1, 96 cells (default + hardened, r1+r2).

Bundle dir: `evidence/live-2026-11-04/opencode-live/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### musecode-n3-rerun

Muse Code n3 rerun, 39 runs. PASS 13 / FAIL 26, harm 7. n3 pilot superseded, not sealed.

Bundle dir: `evidence/live-2026-11-04/musecode-n3-rerun/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### copilot-live

Copilot deletion series (14) + smoke (1). Series PASS 9 / HARM 5.

Bundle dir: `evidence/live-2026-11-04/copilot-live/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### gemini-live

Gemini cheaper 7-scenario series, 14 cells. PASS 11 / HARM 2 / NO-DECISION 1.

Bundle dir: `evidence/live-2026-11-04/gemini-live/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### adapters-v1

v1 adapter results, 120 decisions (5 harnesses x 24). PAPER route -- decisions only, no effects.

Bundle dir: `evidence/live-2026-11-04/adapters-v1/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### claudecode-live

Claude Code live full series, 48 cells. PASS 27 / HARM 6 / ND 13 / OVERBLOCK 2 (13 corrected verdicts; originals in cells).

Bundle dir: `evidence/live-2026-11-04/claudecode-live/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### gemini-live-full

Gemini full 48-cell matrix. PASS 17 / HARM 28 / ND 3. Separate from the 14-cell series.

Bundle dir: `evidence/live-2026-11-04/gemini-live-full/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### copilot-full

Copilot full 48-cell matrix, AS-RUN. PASS 13 / HARM 25 / ND 10 (re-analysis 23/25/0 is a note only).

Bundle dir: `evidence/live-2026-11-04/copilot-full/` (bundle.json + bundle.json.sig + bundle.json.sig.json + SUMMARY/runners).

### codex-live-v1

Codex live v1, 48 cells. PASS 15 / EXECUTED 19 / NO-DECISION 14, harm 19. Route: workspace-write, model gpt-5.6-sol requested.

Bundle dir: `evidence/live-2026-11-04/codex-live-v1/` (bundle.json + bundle.json.sig + bundle.json.sig.json + package manifests).

### musecode-v1

Muse Code live v1, 48 cells (v1.1 corrected tallies; v1.0 superseded). PASS 23 / EXECUTED 4 / NO-DECISION 17 / OVERBLOCK 4, harm 4. Read tool is the harm channel; zero shell executions anywhere.

Bundle dir: `evidence/live-2026-11-04/musecode-v1/` (bundle.json + bundle.json.sig + bundle.json.sig.json + package manifests).

## Format: live-bundle.v1

Each bundle.json carries normalized verdict cells (decisions, verdicts, booleans, rule
names, hashes, counts), a Merkle root + inclusion proofs, recomputed tallies, a file
manifest, caveats, exclusions, and provenance. Cells are NOT verbatim transcripts:
tool output, model text, transcripts, fixture contents, session ids, and absolute local
paths are excluded by design (fake credential fixtures trip secret scanners; session ids
are not evidence). Each cell carries source_path + source_sha256 of the original record
bytes, so a holder of the original can confirm the match. Originals remain at their source
locations (branches listed in each bundle's provenance, or local workdirs).

Merkle construction reuses the repo's own primitives (tools/schemas_v1.py: leaf =
SHA256(0x00 || canonical_json), node = SHA256(0x01 || left || right)); detached Ed25519
signatures reuse tools/bundle_signing.py with the published project key
(40004a96...3326, fingerprint 0c0ab7b5...0e83 -- see docs/SIGNING.md).

Deviation from docs/SIGNING.md, stated plainly: tools/build_evidence_bundle.py and
tools/verify_bundle.py are Codex-Day-2 / finding.v1-specific and cannot express live
cells, so these bundles use a new live-bundle.v1 format with a new standalone verifier
(verify_live_bundle.py in this directory) instead of forcing live cells into finding.v1.
The Merkle construction, the detached-signature helper, and the published public key are
exactly the repo's own.

## Verify

From a checkout of this branch, per bundle:

```
python3 evidence/live-2026-11-04/verify_live_bundle.py evidence/live-2026-11-04/<bundle>/
```

Exit 0 requires: signature valid over the exact bundle bytes, every leaf + inclusion proof
recomputes to the recorded root, tallies recompute from cells, every manifest file matches,
and bundle.json trips no secret pattern. Every bundle on this branch was verified this way
at build time before signing was reported.

## Already sealed (verified, NOT re-sealed)

- Codex postfix `evidence/postfix-2026-10-22/bundle.json` (41 findings, root
  `5a974fe6729b8203319bb7c493a27f89bb501c663ca68bd2f02676045c32060e`): Merkle + proofs
  recompute, detached post-seal attestation VALID (unsigned bundle + valid attestation, as
  SIGNING.md states).
- Amp oracle `evidence/amp-2026-10-22/bundle.json` (52 findings, root
  `cb6eccf0dc9a75bcd8a0343c99b247c4a7c7d0cb09c75e4a01ae6a0ec8a97cf6`): Merkle + proofs
  recompute, detached signature VALID, state signed.
- Day-6 `evidence/day6-2026-10-26/bundle.json` (41 findings, root
  `003bfbb3256032c5febef2559636393d671d75c56ee79788d2d594a38c2d3b32`): Merkle + proofs
  recompute; no detached signature (expected unsigned state, Merkle-only).

All three re-verified fresh via the git/blobs API during this sealing pass (contents-API
downloads mangle binary .sig files; blobs API returns exactly 64 bytes).

## Notes from this pass

- During this pass the Amp, Claude, Gemini-full, and Copilot-full packages merged to main
  (main d92c7af5). Amp merged WITH records (all 48 branch record blobs verified identical to
  main's copies by git SHA); the other three merged package-only (records stay branch/local).
  Bundles were sealed from branch/local sources; none of the main-sourced bundle files changed
  in that merge.
- Omnigent harm_total is 30 while executed is 29: the meta-r2 V1-11 TIMEOUT cell's record flags
  harm=True with effect_happened=False. The bundle faithfully carries the record's flag; the
  verdict tally (29 executed) is the binding count.
- The two runner files that first tripped the builder's secret scan (Gemini series_runner_full.py,
  Copilot full_runner.py) contain only explicitly-FAKE fixture headers ("BEGIN FAKE ... PRIVATE
  KEY") whose bodies are per-cell canary variables -- not real keys. The scan pattern was narrowed
  to exclude FAKE headers (same narrowing in the branch verifier); no real secret was found in any
  bundle file.
- Claude harm uses verdict-based harm (FAIL_HARM = harm): the records' harm_evidence flag is False
  for all 48 cells including the 6 FAIL_HARM cells, so it is not the harm indicator.

## Afternoon pass (Codex + Muse v1)

Codex live v1 (48 cells) and Muse Code live v1 (48 cells, v1.1 corrected tallies) sealed and merged to main in the afternoon pass; the v1_runner.py manifest line that trips the verifier pattern is explicitly-FAKE fixture content (same class as the morning narrowing); both bundle.json files are secret-scan clean.

## Explicitly NOT sealed here

- Claude Nov 3 smoke as a standalone item (publish decision deferred; sealing is not publishing).
  The smoke.json in claudecode-live is the Nov 4 rebuild's pre-matrix gate, not the Nov 3 smoke.
- Cursor (no live cells) and native Gemini (no live cells; 3 failed attempts, closed).
- Per-bundle extras listed in each bundle's exclusions (pilots, transcripts, logs, proxies,
  scratch fixtures, halted attempts, in-flight cells).
