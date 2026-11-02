# Security policy

FinePrint is a measurement instrument, not an enforcement tool. It never
executes commands: `check_command` evaluates policy text, and the check
runner only probes a harness's own decision oracle.

## Reporting a vulnerability

Open a private security advisory on GitHub (Security tab → Report a
vulnerability) rather than a public issue, if the issue could help someone
evade a real policy. Include the harness + version, the policy, the
command, and what the checker decided versus what you expected.

## Scope notes

- A finding that a policy gives **unknown** for a command is a coverage
  finding about that policy, not a vulnerability in FinePrint — unknown
  is the honest answer, and the tool reports it as such.
- Sealed evidence bundles are content-addressed (Merkle roots); a bundle
  whose root does not match its published value should be treated as
  untrusted and reported.
- This repo contains no credentials, tokens, or private data. If you
  find anything that looks like one, report it as above.
