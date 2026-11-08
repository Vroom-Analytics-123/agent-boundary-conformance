# FinePrint free gate — the bouncer (and the tripwire in front of it)

Plain words first. A **gate** is a guard that says yes or no before a
command runs. The free gate has two parts:

- **The tripwire** is a fast pre-check. It reads the command and its
  arguments and refuses the ones that match a known-dangerous pattern
  — before anything runs.
- **The wall** is the enforcement. The command runs inside a sandbox
  built from the operating system's own `unshare` tool, so the
  protected targets do not exist from its perspective. A command that
  hides what it wants inside a script — so the tripwire cannot see
  it — is still stopped by the wall.

The tripwire is fast. The wall is what actually stops the harm. You
get both with one command.

## The default: a protective denylist (antivirus for agents)

Out of the box the wall blocks known-dangerous patterns, derived
from Catalogue v1 and the issues we measured. Normal work anywhere
is allowed by default. This is the default policy — no settings
needed:

| What is blocked | Rule | Example |
|---|---|---|
| SSH keys and config | DENY-CRED-SSH | `~/.ssh/id_rsa` |
| AWS credentials | DENY-CRED-AWS | `~/.aws/credentials` |
| `.env` files (secrets) | DENY-CRED-ENV | any `.env` |
| PEM private keys | DENY-CRED-PEM | any `*.pem` |
| SSH private key files | DENY-CRED-KEY | `id_rsa`, `id_ed25519` |
| Stored git credentials | DENY-CRED-TOKEN | `.git-credentials` |
| The protected records file | DENY-RECORDS | `records.txt`, `records/health` |
| Destructive delete | DENY-DELETE | `rm -rf …` |
| Secure delete | DENY-SHRED | `shred …` |
| Unlink (the bypass around the `rm` filter) | DENY-UNLINK | `unlink …` |
| Unapproved deploy | DENY-DEPLOY | any command named `*deploy*` |
| Copying a protected file out | DENY-EXFIL | `cp ~/.ssh/id_rsa /tmp/x` |

Run `fineprint gate definitions` to see the list in force, with its
version. New discovered issues become new rules in a signed
definitions pack (below).

## Wrappers are unwrapped

The tripwire checks the command that would actually run, not just
the first word on the line. `sudo rm -rf …`, `env rm -rf …`, and
`bash -lc "rm -rf …"` are all refused with DENY-DELETE, exactly like
a plain `rm -rf …` — the tripwire unwraps `sudo`/`doas`, `env`,
`su -c`, `nice`/`time`/`xargs`, and shells with `-c`, and re-checks
the inner command (including a second command after `;`/`&&`/`||`
and a command hidden in `$(…)` or backticks). A command hidden
inside a script file (`bash deploy.sh`) is still out of scope for
the tripwire — the wall hides the protected paths, and
deploy-via-script is recorded as not-covered, never as a hold.

## One command, locally

```bash
fineprint gate run -- cat notes.txt
```

That is the whole thing. No settings needed. (Run `fineprint init
--gate` once to save the policy as `fineprint-gate.json`, so you can
see it and change it.)

What you will see when it allows:

```
policy: built-in default (protective denylist — normal work anywhere is allowed, known-dangerous patterns are blocked; see `fineprint gate definitions`) — run `fineprint init --gate` to save it as fineprint-gate.json
```

and then the command's own output. Exit code 0.

What you will see when the tripwire refuses (a credential read on
the command line):

```
policy: built-in default (protective denylist — ...)
GATE: DENY — file_read of a protected path: '/home/you/.ssh/id_rsa' resolves to '/home/you/.ssh/id_rsa' (rule DENY-CRED-SSH)
refusing to run: cat /home/you/.ssh/id_rsa
```

Exit code 2. The command never ran. The rule id is printed, and
the same action will always be denied — deterministic, not a
judgment call.

What you will see when the wall refuses (the command tries something
inside that is protected — here a script that reads the SSH key
without naming it on the command line, so the tripwire could not
see it):

```
policy: built-in default (protective denylist — ...)
Traceback (most recent call last):
  File "read_key.py", line 1, in <module>
    print(open(os.path.expanduser("~/.ssh/id_rsa")).read())
FileNotFoundError: [Errno 2] No such file or directory: '/home/you/.ssh/id_rsa'
```

Exit code 1 — the command's own exit code, passed through. The file
does not exist from inside the wall, so the read fails and nothing
leaks. The wall does not print its own DENY line for this: the
filesystem itself says no.

One question, without running anything:

```bash
fineprint gate check --file ~/.ssh/id_rsa   # DENY, exit 2 (rule DENY-CRED-SSH)
fineprint gate check --file notes.txt       # ALLOW, exit 0
fineprint gate check --host example.com     # ALLOW (not denied)
```

## Folder confinement (opt-in, not the default)

If you want the stricter mode — the agent may only touch certain
folders and hosts — use `--confine`:

```bash
fineprint gate run --confine -- cat notes.txt      # allows (inside the scope)
fineprint gate run --confine -- cat /etc/passwd    # DENY, exit 2 (rule CONFINE-PATH)
```

Or set `"mode": "confine"` in `fineprint-gate.json` (with
`allowed_paths` / `allowed_hosts`). The denylist still applies on
top in confine mode, so a protected file inside the allowed scope
is still blocked. In confine mode with no hosts allowlisted there
is no network at all; with hosts allowlisted, only those hosts are
reachable.

## Your policy file

`fineprint-gate.json` (written by `fineprint init --gate`):

```json
{
  "mode": "deny",
  "denied_paths": [],
  "denied_hosts": [],
  "allowed_commands": [],
  "allowed_paths": ["."],
  "allowed_hosts": []
}
```

- **mode**: `"deny"` (the default) or `"confine"` (opt-in).
- **denied_paths / denied_hosts**: your own extra blocks, added to
  the definitions (globs for paths, exact hosts).
- **allowed_commands**: command patterns that override the denylist
  — for example `"deploy.sh"` lets your own deploy script run.
  Use it for a deploy you have approved, not to silence a rule you
  have not read.
- **allowed_paths / allowed_hosts**: used only in confine mode.
  `"."` means the current directory.

## Definitions: signed, versioned rule packs

The denylist is a versioned pack of rules. The built-in pack is v1
(`2026-11-07`). New discovered issues become new rules in a new
pack, signed with the maintainers' Ed25519 key (the public key is
published in `docs/SIGNING.md`). The wall verifies the signature
before applying a pack and **never applies an unverified one** — a
pack with no signature, a bad signature, or a signature from the
wrong key is refused, and the gate refuses to run rather than
silently using stale rules.

How you update: a new pack ships with a FinePrint release (git pull,
or a new release). The wall checks for it on every run
(`fineprint-definitions.json` in the repo, or in your working
directory) and applies it when it verifies. There is no live network
update check.

What is in force right now:

```bash
fineprint gate definitions
# definitions: v2026-11-07 (built-in)
# rules: 11
#   DENY-CRED-SSH    path    SSH private keys and config
#   ...
```

## Notifications: every blocked attempt, readable

Every blocked attempt is a structured event in the audit log: what
the agent tried, which rule stopped it, and the fact that the same
action will always be denied. Read it as notifications:

```bash
fineprint gate log --log audit.jsonl
# audit log audit.jsonl: valid (4 entries)
# tried rm -rf notes.txt -> blocked by rule DENY-DELETE -> will always be blocked
# wall up: deny mode, definitions v2026-11-07 (built-in), 3 hidden targets, egress shared (no hosts denied)
# wall down: exit 0
```

The log is hash-chained (each entry hashes the previous one), so an
edit to an earlier entry breaks verification of everything after
it. Check the chain with:

```bash
fineprint gate verify-log --log audit.jsonl
# audit log audit.jsonl: valid
```

## One step, in CI

```yaml
- name: gate guards a whole command
  run: python3 fineprint gate run -- cat README.md
- name: wall denies a script that reads the SSH key
  continue-on-error: true
  run: python3 fineprint gate run -- python3 read_key.py
```

See `.github/workflows/fineprint-check.yml` (the `gate` job) for the
working example. A denied step fails the job unless you set
`continue-on-error: true` — use that only for the demonstration
step, never for the real guard.

## How the wall works (short version)

The wall is built from the operating system's own tools — it does
not invent a sandbox. Read `tools/fineprint_wall.py` (about 400
lines) to see all of it.

- **Filesystem:** the wall starts the command in a new user and
  mount namespace (`unshare`). Before the command runs, the
  protected targets (denylist mode) — or everything outside the
  allowed scope (confine mode) — get covered: an empty folder over
  directories, an empty file over files. From inside, the covered
  things do not exist. The command then runs with the capability to
  mount things removed (`CAP_SYS_ADMIN` dropped), so it cannot
  uncover them again.
  - **Where the denylist looks (the bound):** the wall hides the
    protected targets in the working directory (the project), in
    `/tmp` and `/var/tmp`, and in the well-known credential locations
    in your home directory (`~/.ssh`, `~/.aws`, `~/.env`,
    `~/.git-credentials`, `id_rsa*`, `id_ed25519*`). A protected
    file in another project directory is NOT hidden unless it is
    under the working directory or `/tmp`. That bound is deliberate:
    walking the whole home directory found ~3,000 fixture files and
    made every run mount ~3,000 covers (~10s). If you need a target
    outside that bound hidden, add it to `denied_paths` in
    `fineprint-gate.json` — or use `--confine`, which hides
    everything outside the allowed scope.
- **Network:** in confine mode with no hosts allowlisted, the wall
  also starts a new network namespace with no route at all — nothing
  can be reached, not even localhost. With hosts allowlisted
  (confine) or hosts denied (deny), the wall starts a small
  localhost proxy that only forwards what the policy allows, and the
  command's network settings point at it. In deny mode with no hosts
  denied, the network is shared (normal work needs it).
- **Audit:** the wall writes `WALL_START` (the mode, the
  definitions version, what was hidden, the egress mode) and
  `WALL_END` (the exit code) to the same hash-chained log as the
  tripwire. Proxy denials are logged with the host and the rule.

## What the wall is NOT — read this before trusting it

The wall enforces **scope** (paths and hosts), not intent. An agent
that misuses a file **inside** the allowed scope (or a normal file
in denylist mode) is out of scope for the wall. That is Check's job
(Catalogue v1 measures whether the agent follows its own rules).

- **It does not hide the process list.** The agent can see host
  process listings in `/proc`. It cannot inspect or stop those
  processes (that needs a capability it does not have inside the
  wall). The hardened gate adds a process namespace.
- **The proxy controls egress only for tools that honor proxy
  settings** (curl, Python, Node, most command-line tools). A
  process that ignores those settings and opens a direct network
  connection can still reach the network when the network is shared
  (deny mode, or confine mode with hosts allowlisted). With **no**
  hosts allowlisted in confine mode there is no network at all, so
  there is nothing to bypass. True socket-level egress blocking (a
  network namespace plus a private network link) is the hardened
  gate.
- **The agent runs as root inside its own user namespace.** The
  covers are protected by dropping the mount capability before the
  command runs. If neither `setpriv` nor `capsh` is available on the
  machine, the drop is skipped and a warning is printed — the
  unmount bypass is then open. Both tools ship with the same package
  as `unshare` (util-linux), so this should not happen on Linux.
- **System files stay visible.** `/usr`, `/etc`, and the rest are
  needed to run anything, so they are visible inside the wall. The
  wall hides your protected files — not the operating system's
  files. A symlink to a protected file dangles, because the target
  does not exist inside; a symlink to a normal file still resolves.
- **If `unshare` is missing, the gate refuses to run.** It never
  silently falls back to the tripwire. The error names the missing
  tool. `unshare` ships with Linux by default (including GitHub's
  ubuntu runners); if your machine does not have it, install
  util-linux — or run with `--no-wall` to use the tripwire only, and
  know that you are doing so (it prints a warning).
- **A definitions pack that does not verify refuses the run.** If
  you see `definitions: ... does not verify`, delete the pack file
  or replace it with a signed one from a FinePrint release. The gate
  will not run on unverified rules.

## When it is red

1. **Tripwire DENY (exit 2, "refusing to run"):** a path, host, or
   command on the command line matched a rule. Read the DENY line —
   it names the rule. If the command was supposed to do it (your
   own deploy script), add it to `allowed_commands` in
   `fineprint-gate.json` and run again. If not, the gate did its job.
2. **Wall deny (the command fails inside, "No such file or
   directory"):** the command tried to reach something protected
   without naming it on the command line (a script, a symlink, a
   config file). The file does not exist from inside the wall. Find
   out why the command wanted it.
3. **Wall setup failure (exit 125 or exit 3, "wall: ..."):** the
   sandbox could not be built — read the message. Common causes: no
   `unshare` on PATH, an allowed path that does not exist (confine
   mode), or a working directory outside the allowed scope (confine
   mode).
4. Check the audit log (`fineprint gate log --log audit.jsonl`) to
   see what was tried, which rule stopped it, and the boundary that
   was in force.
