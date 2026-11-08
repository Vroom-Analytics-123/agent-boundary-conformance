# FinePrint free gate — one wrapper command, defaults on

Plain words first. A **gate** is a guard that says yes or no before a
command runs. The free gate is a **wrapper**: you run your command
through it, it looks at what the command is about to touch, and it
either lets it run or refuses — and writes the decision down in a log
you can check later.

## One command, locally

```bash
fineprint gate run -- cat notes.txt
```

That is the whole thing. No settings needed: with no policy file, the
gate allows only the current directory and no network hosts. (Run
`fineprint init --gate` once to save that policy as
`fineprint-gate.json`, so you can see it and change it.)

What you will see when it allows:

```
policy: built-in default (this directory only, no hosts) — run `fineprint init --gate` to save it as fineprint-gate.json
```

and then the command's own output. Exit code 0.

What you will see when it refuses:

```
policy: built-in default (this directory only, no hosts) — run `fineprint init --gate` to save it as fineprint-gate.json
GATE: DENY — file_read outside allowed paths: '/etc/passwd' resolves to '/etc/passwd'
refusing to run: cat /etc/passwd
```

Exit code 2. The command never ran — `cat` never saw the file. That
is the point: the refusal happens before the effect, not after.

One question, without running anything:

```bash
fineprint gate check --file /etc/passwd     # DENY, exit 2
fineprint gate check --file README.md       # ALLOW, exit 0
fineprint gate check --host pypi.org        # depends on your policy
```

## One step, in CI

```yaml
- name: gate allows a file inside the repo
  run: python3 fineprint gate check --file README.md
- name: gate denies a file outside the allowed scope
  continue-on-error: true
  run: python3 fineprint gate check --file /etc/passwd
```

See `.github/workflows/fineprint-check.yml` (the `gate` job) for the
working example. A denied step fails the job unless you set
`continue-on-error: true` — use that only for the demonstration step,
never for the real guard.

## Your policy file

`fineprint-gate.json` has two lists:

```json
{
  "allowed_paths": ["."],
  "allowed_hosts": []
}
```

- **allowed_paths**: folders the guarded command may touch. `"."`
  means the current directory. Add a folder to allow it.
- **allowed_hosts**: hosts the command may fetch from. Empty means
  none. Add `"pypi.org"` to allow it.

Everything not listed is denied. That is called deny-by-default, and
it is the whole idea: you list what is allowed, and the rest is no.

## The audit log

Every decision is appended to a log file (`--log audit.jsonl`), one
line per decision, each line chained to the one before it with a hash.
If anyone edits an earlier line, the chain breaks and verification
fails. Check it with:

```bash
python3 -c "import sys; sys.path.insert(0, 'tools'); import fineprint_gate as G; print(G.AuditLog.verify('audit.jsonl'))"
```

## What the free gate is NOT — read this before trusting it

The free gate is a **wrapper-level guard**. It stops the common paths
and proves the decision was recorded. It is not a security boundary:

- It checks what a command is **asked** to touch — the words on its
  command line. It does not watch what the command actually does
  while it runs. A command can still read a file it does not name
  (from a script, an environment variable, a config file).
- It does not stop shell tricks. `fineprint gate run` takes the
  command's words directly (no shell), so redirections like `>
  /etc/passwd` cannot even be expressed through it — but a script
  the command runs can do whatever the script says.
- It does not watch the network. It checks hosts named on the command
  line (`curl https://...`); a program that opens its own connection
  is not seen.
- A file link (symlink) created after the check, pointing outside the
  allowed scope, is not caught. The check happens once, before the
  run; the filesystem can change during it.
- It is not the hardened gate. The hardened gate (sandbox + egress
  proxy + filesystem boundary — the thing that actually stops an
  effect) is the paid product, and it is built and sold separately.
  The free gate never pretends to be it.

Use the free gate for what it is: a tripwire and an audit trail for
the obvious cases, in local use and in CI. If you need a boundary
that holds against a hostile or careless agent, that is the paid
gate — ask about it, do not rely on this one.

## When it is red

1. Read the DENY line. It names the path or host and why it was
   refused (outside the allowed scope, traversal, not allowlisted).
2. Decide: was the command supposed to touch that? If yes, add the
   path or host to `fineprint-gate.json` and run again. If no, the
   gate did its job — find out why the command asked for it.
3. Check the audit log to see the decision and everything before it.
