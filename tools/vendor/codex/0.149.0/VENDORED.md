# Vendored pinned oracle — codex-cli 0.149.0

**Status:** vendored and sha256-verified 2026-10-21 (Day-5 run).

## What is here

| File | Content |
|---|---|
| `bin/codex` | The pinned native oracle binary, `codex-cli 0.149.0` (x86_64-unknown-linux-musl). **Git-ignored (see below); present on disk.** |
| `codex-package.json` | Upstream vendor manifest for this platform package (committed). |
| `VENDORED.md` | This file (committed). |

## Verification (recorded at restore time)

```
$ tools/vendor/codex/0.149.0/bin/codex --version
codex-cli 0.149.0
$ sha256sum tools/vendor/codex/0.149.0/bin/codex
bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827
```

The sha256 matches the Day-2 sealed bundle's `pinned.codex_binary_sha256`
(`evidence/day2-2026-10-22/bundle.json`) byte-for-byte. The binary was
restored via the npm distribution channel (see recipe); the Day-4 conclusion
that 0.149.0 was "not recoverable" is superseded — the wrapper package's
platform tarball IS the recoverable distribution channel.

## Reproducible fetch recipe (produces byte-identical bits)

npm tarballs are immutable per published version, so this recipe is a full
recovery path for the pinned binary:

```bash
cd /tmp && mkdir codex-restore && cd codex-restore
npm pack "@openai/codex@0.149.0-linux-x64"   # alias: @openai/codex@0.149.0-linux-x64
mkdir lin && tar -xzf openai-codex-0.149.0-linux-x64.tgz -C lin
sha256sum lin/package/vendor/x86_64-unknown-linux-musl/bin/codex
# must print bbc3341e44c9ead340ed9570c17be936e37870f570751a941699ffd04d672827
cp lin/package/vendor/x86_64-unknown-linux-musl/bin/codex \
   <repo>/tools/vendor/codex/0.149.0/bin/codex
```

The `@openai/codex` wrapper (`npm pack @openai/codex@0.149.0`) resolves the
native binary through its `optionalDependencies`
(`@openai/codex-linux-x64` → `npm:@openai/codex@0.149.0-linux-x64`); the
platform tarball above is what actually ships the binary.

## Why the binary itself is git-ignored

`bin/codex` is 258 MB. GitHub rejects any blob > 100 MB, so committing it
would permanently break this repo's push path (the Git Data API mirror).
The binary IS vendored into the repo's evidence tooling path on disk and is
part of the reproducible workflow: `tools/pin.py` prefers it and verifies its
sha256 on every use. The committed recipe above plus the pinned hash
reproduces the identical bytes anywhere.

## Pin-checklist step this adds (see docs/PIN_CHECKLIST.md)

> At pin time, vendor the pinned oracle binary (or a reproducible recipe +
> verified sha256) into `tools/vendor/<harness>/<version>/` BEFORE any oracle
> work runs. No oracle work may run on a binary whose sha256 does not match
> the pin.
