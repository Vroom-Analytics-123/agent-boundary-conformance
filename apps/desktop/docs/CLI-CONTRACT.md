# FinePrint CLI contract — as verified against the real CLI

This is the contract the desktop app is built against. Every claim
below was verified live against the sibling CLI checkout
(`~/workspace/fineprint-free-check`, branch `free-wall`, 2026-11-07)
and the app's own integration suite (`tests/test-real-cli.js`,
`FINEPRINT_REAL_CLI=1`). If the CLI changes, this file and the tests
change with it — the app never guesses.

## Commands

| Command | Exit codes |
|---|---|
| `fineprint check [options]` | 0 pass / 2 blocked / 3 unknown |
| `fineprint init [--harness H] [--rules FILE] [--gate]` | 0; writes `fineprint-gate.json` for `--gate` |
| `fineprint verify BUNDLE` | 0 = seal valid |
| `fineprint report BUNDLE` | readable verdict table |
| `fineprint gate run --policy P --log L [--no-wall] [--confine] -- CMD...` | 2 tripwire deny, 3 error / wall unavailable, 125 wall setup failed, otherwise the command's own exit code |
| `fineprint gate check --file P \| --host H` (+ `--policy P`) | 0 allow / 2 deny / 3 error |
| `fineprint gate verify-log --log FILE` | 0 valid / 1 invalid / 3 error |
| `fineprint gate definitions` | 0; prints the definitions version in force |
| `fineprint gate log --log FILE` | renders the audit log in plain words |
| `fineprint harnesses` | lists the known agents |

`--confine` on `gate run` switches the policy to confine mode for
that run. `--no-wall` is the explicit, labelled tripwire-only run
(not enforced). When `--policy` is omitted the CLI uses
`./fineprint-gate.json` when it exists, else the built-in deny default.

## Policy file (`fineprint-gate.json`)

```json
{
  "$comment": "...",
  "mode": "deny",
  "denied_paths": [],
  "denied_hosts": [],
  "allowed_commands": [],
  "allowed_paths": ["."],
  "allowed_hosts": []
}
```

- `mode` — `"deny"` (default; unknown values fall back to `"deny"`)
  is the protective denylist: anything the signed definitions name
  is denied, everything else is allowed. `"confine"` (opt-in) is the
  folder allowlist: anything outside the allowed paths/hosts is
  denied, on top of the denylist.
- `denied_paths` — fnmatch globs on the resolved path (your own blocks,
  on top of the definitions). `denied_hosts` — exact hosts, ditto.
- `allowed_commands` — command basenames or globs that override the
  denylist for one command (e.g. your deploy script).
- `allowed_paths` / `allowed_hosts` — only enforced in confine mode.

Decision order (deny-first): definitions rules, then the policy's
own denied lists, then (confine mode only) the allowlist. Unknown
action kinds are denied. A command is checked as a whole first
(`check_command`): an explicitly allowed command wins; a copy/send
command (`cp`, `scp`, `rsync`, `curl`, `wget`) naming a protected
file is denied as `DENY-EXFIL`; then the definitions command rules.

## Definitions

- Pack file `fineprint-definitions.json`: `{version, rules, signature}`.
  The signature is Ed25519 over the canonical JSON of
  `{version, rules}`, made with the maintainers' key whose public half
  is published in `docs/SIGNING.md` (the same key that signs the
  sealed evidence bundles; fingerprint
  `0c0ab7b5…0e83`, public key
  `40004a96827ae90e5ad4ae36da1414aa80d83625818668604803ba60f3393326`).
- The wall verifies the signature before applying a pack and NEVER
  applies an unverified one. No pack file found → the built-in v1
  rules, version `2026-11-07`, source `built-in`.
- Update channel: a new pack ships with a FinePrint release (git pull
  or a new release). There is no live network update check.
- `fineprint gate definitions` prints e.g.:
  `definitions: v2026-11-07 (built-in)` + `rules: 11` + the rule list.

Built-in v1 rules (11):

| Rule | Kind | What it blocks |
|---|---|---|
| `DENY-CRED-SSH` | path `**/.ssh`, `**/.ssh/**` | SSH private keys and config |
| `DENY-CRED-AWS` | path `**/.aws`, `**/.aws/**` | AWS credentials |
| `DENY-CRED-ENV` | path `**/.env` | .env files (secrets) |
| `DENY-CRED-PEM` | path `**/*key*.pem`, `**/*private*.pem` | PEM private keys |
| `DENY-CRED-KEY` | path `**/id_rsa*`, `**/id_ed25519*` | SSH private key files |
| `DENY-CRED-TOKEN` | path `**/.git-credentials` | stored git credentials |
| `DENY-RECORDS` | path `**/records.txt`, `**/records/health` | the protected records file |
| `DENY-DELETE` | command `rm` + any of `-r -f -rf -fr -R --recursive --force` | destructive delete |
| `DENY-SHRED` | command `shred` | secure delete |
| `DENY-UNLINK` | command `unlink` | the bypass around the rm filter |
| `DENY-DEPLOY` | command glob `*deploy*` | unapproved deploy |

Plus two rules the gate produces (not listed as rules):
`DENY-EXFIL` (copy/send of a protected file) and the policy's own
`DENY-PATH` / `DENY-HOST`, and `CONFINE-PATH` / `CONFINE-HOST` in
confine mode. Path patterns are Python fnmatch globs (`*` matches
`/` too). Command rules match the basename of argv[0]; a rule with
`any_flag` fires only when one of those flags appears as a whole
argv token.

## Audit log

Append-only JSONL. Each entry hashes the previous entry's hash, so
any edit breaks verification of everything after. Entry shape:

```json
{"action": {"kind": "file_read", "target": "/tmp/x/records.txt"},
 "allowed": false, "reason": "...", "note": "pre-flight: ...",
 "prev_hash": "<hex>", "hash": "<hex>",
 "deterministic": true, "rule": "DENY-RECORDS"}
```

- `hash` = sha256 of Python's `json.dumps(entry-without-hash,
  sort_keys=True)` — **spaced** separators (`", "`, `": "`), sorted
  keys, non-ASCII escaped. The compact form hashes differently; the
  app's `core/audit.js` matches the spaced form (verified against a
  real gate entry, hash `c2651ed7…`, in `tests/test-audit.js`).
- Denied entries carry `"deterministic": true` and `"rule": "<id>"`.
  Allowed entries carry neither.
- `WALL_START` entries carry top-level `mode`, `definitions`,
  `hidden_paths`, `egress`. `WALL_END` carries top-level `exit_code`.
- `gate verify-log` verifies the chain; `gate log` renders entries as
  "tried X -> blocked by rule Y -> will always be blocked".

## The wall

Linux-only (`unshare` user+mount+net namespaces). Two modes:

- `deny` (default): the denylisted targets are hidden inside the
  wall; the network is shared with a proxy in denylist mode (denied
  hosts blocked, everything else allowed).
- `confine` (opt-in): everything outside the allowed scope is hidden
  too; no hosts allowlisted → `unshare --net` (no network at all).

The wall verifies the definitions before running and refuses
(exit 3) instead of running unprotected when the wall cannot run or
the definitions do not verify.

On macOS/Windows the wall runs inside a Linux runtime: Docker
Desktop or WSL2 (Windows). There is no native macOS/Windows wall.

## What the app does with this

- It never vendors or copies the CLI. It finds it on PATH or from
  Settings, and drives it only through the commands above.
- It writes policies in exactly the shape above (`mode: "deny"` by
  default; `mode: "confine"` only when the user opts in; `--confine`
  passed to `gate run` in that case).
- It reads the definitions in force from `gate definitions` and
  embeds a reference copy of the built-in v1 rules for labelling feed
  items only — it never enforces anything itself.
- It probes denylist support (`gate check` on a temp denied file)
  and shows the result honestly instead of claiming protection the
  connected CLI cannot enforce.
- It verifies every audit log it reads through `core/audit.js`
  (same hash form as the CLI) and shows the log's own `rule` and
  `deterministic` fields in the feed.
