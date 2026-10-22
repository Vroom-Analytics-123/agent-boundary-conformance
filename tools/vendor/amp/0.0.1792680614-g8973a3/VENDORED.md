# Vendored pinned oracle — amp 0.0.1792680614-g8973a3

**Status:** vendored and sha256-verified 2026-10-22 (Amp second-oracle spike).

## What is here

| File | Content |
|---|---|
| `bin/amp` | The pinned native oracle binary, amp `0.0.1792680614-g8973a3` (linux-x64). **Git-ignored (see below); present on disk.** |
| `install.sh` | Amp's official installer as fetched 2026-10-22 (committed; the fetch recipe). |
| `VENDORED.md` | This file (committed). |

## Verification (recorded at install time)

```
$ tools/vendor/amp/0.0.1792680614-g8973a3/bin/amp --version
0.0.1792680614-g8973a3 (released 2026-10-22T14:50:14.000Z)
$ sha256sum tools/vendor/amp/0.0.1792680614-g8973a3/bin/amp
89304a6e5bc739807062433a28bba5a98dc8dfbae05d8674df06a465103c8f3f
```

## Reproducible fetch recipe (produces byte-identical bits)

The installer downloads `cli-version.txt`, the platform binary, and its sha256
from `https://static.ampcode.com` and verifies the checksum before installing.
Pin the version explicitly with `AMP_VERSION` so the fetch does not float:

```bash
mkdir -p <repo>/tools/vendor/amp/0.0.1792680614-g8973a3/bin
cd <repo>/tools/vendor/amp/0.0.1792680614-g8973a3
# install.sh is committed alongside; or re-fetch: curl -fsSL https://ampcode.com/install.sh
AMP_VERSION=0.0.1792680614-g8973a3 \
AMP_HOME=<repo>/tools/vendor/amp/0.0.1792680614-g8973a3/amp-home \
HOME=<scratch-fake-home> \
bash install.sh
sha256sum amp-home/bin/amp
# must print 89304a6e5bc739807062433a28bba5a98dc8dfbae05d8674df06a465103c8f3f
cp amp-home/bin/amp bin/amp
```

Caveat: unlike npm tarballs, `static.ampcode.com` is a mutable release
channel — the recipe reproduces the pinned bytes only while the vendor keeps
serving that exact version. The vendored on-disk copy + recorded sha256 is the
primary pin; the recipe is the recovery path.

## Why the binary itself is git-ignored

`bin/amp` is ~160 MB. GitHub rejects any blob > 100 MB, so committing it
would permanently break this repo's push path (the Git Data API mirror).
The binary IS vendored into the repo's evidence tooling path on disk and is
part of the reproducible workflow. The committed recipe above plus the pinned
hash reproduces the identical bytes while the vendor serves the version.

## Install-time notes

- The installer was run with `HOME` pointed at a scratch fake-home and
  `AMP_HOME` workspace-local, so its symlink/PATH/profile writes never touched
  the real home. The spike ran `amp permissions test` with no credentials
  present: no account, no login, no API key (see docs/amp-spike-2026-10-22.md).
- `AMP_SKIP_UPDATE_CHECK=1` (or `amp.updates.mode: "disabled"` in settings)
  should be set when driving the pinned binary, so it never self-updates
  out from under the pin.
