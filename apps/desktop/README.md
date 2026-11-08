# FinePrint desktop

A desktop app (macOS + Windows) that makes the free FinePrint wall
usable without a terminal — for engineers **and** for people who never
open a terminal. It is a GUI around the `fineprint` CLI; it does not
reimplement measurement or enforcement.

![FinePrint desktop demo](assets/fineprint-app-demo.gif)

## What it does

- **Home — the notifications feed.** What the agent tried to do,
  what was blocked or stopped, and which rule stopped it. A blocked
  action is always blocked — the same action is denied every time.
  OS notifications too (macOS Notification Center / Windows Action
  Center) when the wall blocks something.
- **Definitions.** The wall verifies signed definition packs; the app
  shows the version in force and the last-updated date, and checks
  for an update. The protection line reads:
  "Protected by FinePrint definitions vX — credential theft,
  destructive deletes, exfiltration, unapproved deploys blocked."
- **Check my setup.** Runs `fineprint check` and shows the verdict
  in plain language.
- **The Wall.** Pick the agent (codex / muse code / claude code),
  pick the folder to guard, see the policy in plain language, click
  Run. Red/green verdicts and the audit log in plain language (what
  was blocked, why).
- **Settings.** The policy editable in plain terms, the CLI path, the
  log location, the definitions status.

**Defaults:** the wall's default is a protective denylist (known-
dangerous patterns). Folder limiting is an **opt-in** toggle —
"Confine the agent to these folders" — off by default.

## Install

1. Install the `fineprint` CLI (see the repo root README) and make
   sure it is on your PATH, or pick its path in Settings.
2. Download the installer for your OS (macOS .dmg / Windows .exe /
   Linux AppImage) from the releases on this branch's CI artifacts,
   and run it. No account, no hosted backend, no telemetry by default.
3. First run: the app finds the CLI on PATH (or asks you to pick
   it), and shows the definitions status and the protection line.

The wall itself is Linux-only (`unshare`). On macOS/Windows the wall
runs inside a Linux runtime: Docker Desktop (macOS/Windows) or WSL2
(Windows). If no wall runtime is available, Check still works and
the Wall screen says so plainly and offers an explicit, labelled
tripwire-only run — never a silent unprotected run.

## Packaging (what exists, what doesn't)

Built in-container from this branch (`apps/desktop/dist/`):

- **macOS .app — BUILT and verified** (`dist/FinePrint-darwin-x64/FinePrint.app`):
  binary + `main.js` present, `CFBundleIdentifier
  com.vroomanalytics.fineprint`. Built with electron-packager.
- **macOS .dmg — NOT built here.** Needs `hdiutil`, which is
  macOS-only. The script builds the .app and says so plainly instead
  of faking a .dmg. The CI workflow runs the same script on
  macos-latest, where the .dmg is produced.
- **Windows .exe (unpacked) — built if Wine is installed; otherwise
  NOT built.** electron-packager and electron-builder both need Wine
  on Linux for the Windows metadata/NSIS steps — without it the
  packager exits 0 and silently produces nothing (a known trap; the
  script checks for the exe and fails loudly). The CI workflow runs
  electron-builder on windows-latest, where the NSIS installer is
  produced natively.
- **Linux — BUILT** (`dist/FinePrint-linux-x64`).

All installers built here are **unsigned**. Signing and notarization
need Anish's Apple Developer account (macOS) and a Windows
code-signing certificate. There is no app icon yet (no .icns/.ico
asset) — the builds use Electron's default icon.

## What was tested

Unit + integration + end-to-end, on real flows (see
`apps/desktop/tests/`). Scenarios, not counts:

- **CLI discovery:** found on PATH; missing → a clear error in plain
  words; a path picked in Settings is used and remembered.
- **Check:** a passing setup shows a green verdict; a broken setup
  names the broken rules; a setup the CLI cannot judge shows
  "could not tell", never a pass. Unmeasured items are listed, not
  hidden.
- **Guarded run, denied:** a command that reads the protected
  records file is denied by the tripwire (`DENY-RECORDS`, exit 2)
  before anything runs — the verdict banner, the feed entry (rule +
  "this will always be blocked"), and the OS notification all show
  it. Verified against the real CLI and against the stub.
- **Guarded run, confine mode:** a command inside the allowed scope
  runs; a command outside it is denied; a script that reads a file
  outside the scope without naming it on the command line is stopped
  by the wall (the tripwire would miss it).
- **Audit log:** a real deny log from the CLI verifies through the
  app's hash-chain checker; a tampered log fails verification.
  The hash form matches the CLI's (Python-spaced JSON).
- **Definitions:** the in-force version is read from the CLI; a
  signed pack verifies; an unsigned or tampered pack is refused.
  The update check compares versions — there is no live network
  feed (new packs ship with a FinePrint release).
- **Policy editing:** deny-mode and confine-mode policies round-trip
  through the app and the CLI; `allowed_commands` lets one command
  through the denylist and nothing else.
- **Wall runtime detection:** native `unshare` wins; Docker is used
  when `unshare` is missing and Docker works; Docker installed but
  not running reports "none" with install guidance. The Docker run
  uses the custom `fineprint-wall:latest` image
  (`apps/desktop/docker/Dockerfile` — Codex + Claude Code
  pre-installed, pinned; Muse Code cannot be baked in, see
  `apps/desktop/docker/README.md`), passes API keys through, and
  lifts the seccomp block on `unshare` inside the container.
- **GUI:** the app launches under Xvfb, renders the Home screen
  (definitions card + empty feed), and the scripted demo flow
  (`electron . --demo`) drives the real UI end to end — see the GIF
  above and `docs/RECORDING.md`.

Run the suite: `cd apps/desktop && npm test` (unit + integration,
stub CLI), and `npm run test:real-cli` (integration against the real
CLI; needs the CLI on PATH or `FINEPRINT_REAL_CLI_PATH`).

## What needs a real Mac/Windows machine

Verified in-container (Linux): all tests above, the real-CLI
integration, the GUI rendering under Xvfb (smoke test:
`packaging/smoke-test.sh`), the demo GIF capture, the macOS .app
build, and the Linux build. Still needs a human on a real machine:

- Installing the .dmg / .exe and launching the app (the in-container
  .app/.exe are built, not installed).
- The Docker wall path on macOS/Windows (Docker is not installed in
  this container, so the Docker runtime branch is unit-tested only).
  The image exists (`apps/desktop/docker/Dockerfile`) but has never
  been built or run end to end — that needs a real Mac.
- OS notification rendering in Notification Center / Action Center
  (the app calls the OS notification API; the feed entry is the
  record either way).
- Code signing and notarization: the installers built here are
  unsigned. Signing needs Anish's Apple Developer account (macOS)
  and a Windows code-signing certificate.
- A proper app icon (.icns for macOS, .ico for Windows) — the builds
  use Electron's default icon until one is made.

## The CLI contract

The app drives the `fineprint` CLI and never vendors it. The full
verified contract — policy shape, definitions format and signing
key, gate commands, audit-log hash form, exit codes — is in
`apps/desktop/docs/CLI-CONTRACT.md`. How to record the demo GIF is
in `apps/desktop/docs/RECORDING.md`.

## Honesty rules the app follows

- Never "safe" or "certified" about any harness. Unknown is a
  first-class verdict.
- No network calls to upstream harnesses, no sign-ins, no
  submissions. The app only talks to the local CLI.
- The wall's limits are shown in the app, not hidden: the denylist
  walk covers the working folder, /tmp, /var/tmp, and the usual
  credential spots in $HOME — a protected file in another project
  folder is not hidden unless you add it to your deny list or turn
  on confinement. The wall enforces scope (which folders and hosts
  the agent can reach), not intent. If the wall cannot run
  (`unshare` missing), the gate refuses instead of running
  unprotected, and the app says so plainly.
