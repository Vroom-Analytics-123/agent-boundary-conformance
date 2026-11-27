# FinePrint seccomp profile — the least-privilege way to let the wall `unshare`

`fineprint-seccomp.json` is Docker's default seccomp profile with exactly
one change: an unconditional `SCMP_ACT_ALLOW` rule for three syscalls —
`clone`, `mount`, `unshare`. It replaces `--security-opt
seccomp=unconfined` wherever the wall runs inside a container. It is the
same shape KiroCrew ships (`docker/seccomp/kirocrew-seccomp.json` — see
the investigation doc §12): the Docker default allow-list extended with
unconditional `unshare`, `clone`, and `mount` rules, "strictly less
permissive than `--security-opt seccomp=unconfined`".

## Why the default profile blocks the wall (VERIFIED, from the profile itself)

Docker's default profile is an allow-list (`defaultAction:
SCMP_ACT_ERRNO`). The three syscalls the wall needs are **not**
unconditionally allowed. They appear in exactly one rule, gated on a
capability:

- `unshare`, `clone`, `mount`, `setns`, `umount`, `bpf`, `clone3` are
  allowed only when the calling process holds `CAP_SYS_ADMIN`
  (`includes: {caps: [CAP_SYS_ADMIN]}`).
- `clone` without `CAP_SYS_ADMIN` is allowed only when **no**
  namespace flag is set (the arg filter masks `0x7E020000`, the sum of
  all `CLONE_NEW*` flags — so a plain fork is fine, a namespace clone
  is not). `clone3` without the capability is denied outright.

So whether `unshare --user --mount` works inside a default container
depends on whether the calling process holds `CAP_SYS_ADMIN` when
seccomp evaluates the call — which varies by runtime (rootful Docker
drops it for the container's init; rootless Docker / Podman run the
container inside a user namespace where its root holds it). That is why
the sources disagree and why the nested-unshare test, not the docs,
settles it (investigation doc §7.2, §12).

The unconditional rule appended here removes the capability gate for
exactly those three syscalls. The kernel's own capability checks still
apply — allowing the syscall through seccomp does not grant the
capability — so the profile is bounded by the same checks that bound
the default. Rule order is what makes the append work: seccomp rules
are evaluated in order and a rule whose `includes` condition is not met
does not match, so a process without `CAP_SYS_ADMIN` falls through the
gated rule to the unconditional one.

Docker's own docs say "it is not recommended to change the default
seccomp profile" — the counterweight, stated plainly. The profile is
the narrowest change that lets the wall start; `seccomp=unconfined`
removes the whole profile. Prefer the profile; keep `unconfined` as the
last resort in the nested-unshare test, where a pass with it and a fail
with the profile is itself a diagnostic (something else the wall needs
is blocked by the default profile).

## Provenance

Derived 2026-11-08 from Docker's default seccomp profile as published
in `moby/profiles`:

- Source: https://github.com/moby/profiles/blob/main/seccomp/default.json
- Upstream sha256:
  `6416b47770785a41ac59073cdc77d9fe98517df2799dc83ef207e622de3053f6`
- Derivation: the upstream file verbatim, plus one appended rule
  (`{"names": ["clone", "mount", "unshare"], "action":
  "SCMP_ACT_ALLOW"}`). The derivation asserted before appending that
  none of the three names was already unconditionally allowed and that
  each was present only in the `CAP_SYS_ADMIN`-gated rule — so the
  append is a real change, not a duplicate.
- This file sha256:
  `ea6494ff98cf40aee9d4c624c41f56dd3db18b968fa0b92d5c13e7c853aee664`
  (61 rules: the upstream 60 + 1).

If the upstream default changes, re-derive from the new file and
record the new upstream sha256 here; do not hand-edit the allow-list.

## Use

```sh
docker run --rm \
  --security-opt seccomp=cloud/docker/fineprint-seccomp.json \
  --security-opt apparmor=unconfined \
  fineprint-wall:cloud claude
```

The `apparmor=unconfined` half is separate and equally needed on
AppArmor hosts (Ubuntu/Debian): Docker also attaches its
`docker-default` AppArmor profile, whose `deny mount` refuses the
wall's first mount with `EACCES` after both unshares succeed
(KiroCrew's docker guide). It lifts only AppArmor's per-container
rules; the seccomp profile, the dropped capabilities, and the wall
itself still apply. On a host without AppArmor it is a no-op. In
Kubernetes the equivalents are `seccompProfile: {type: Localhost,
localhostProfile: <path>}` (load the file on the node first) and
`appArmorProfile: {type: Unconfined}`; a `RuntimeDefault` seccomp
profile blocks `unshare`.

## UNVERIFIED

This profile has never been used in a real `docker run` (no Docker in
the build container). `cloud/nested-unshare-test.sh` tries it before
falling back to `seccomp=unconfined`; run that script on a real Docker
host. Until then the profile is a structural artifact (valid JSON, the
right three syscalls, the right default action — checked by
`cloud/tests/test_cloud_image.py`), not a verified runtime fix.
