# Hermes Agent — gap fixes (DRAFT PR form — not submitted)

*Drafts only. Prepared 2026-10-23 as part of the FinePrint live campaign
(Waves B+C, Stage 2: Hermes LIVE measurement). No PR has been opened, no
patch has been applied to any Hermes checkout, and nothing here is a
conformance claim. Each entry follows the same form: problem, evidence
refs, proposed patch / doc change (sketch), acceptance probes.*

*Harness: Hermes Agent (Nous Research, MIT) — `hermes` CLI,
`github.com/NousResearch/hermes-agent`. Background assessment:
`adapters/hermes-assessment.md` (2026-10-22, DOC-only); draft catalogue
translations: `docs/catalogue/translations-draft/hermes.json`. Live
evidence (when present) is cited per entry from
`evidence/live-campaign-2026-10-23/hermes/`.*

---

## FP-002 — Prompt-form invariants have no deterministic expression

### Problem

Invariants of the form *"prompt before `<deploy_bin> <action_args>`
targeting `<environment>`"* cannot be expressed deterministically in
Hermes. The only owner-authored deterministic terminal rule kind is
`approvals.deny` (an fnmatch glob list in `~/.hermes/config.yaml`) whose
outcome is **forbidden**, never **prompt**. The built-in
dangerous-pattern table does prompt (in `approvals.mode: manual`), but
owners cannot add rows to it. The only owner-authored prompt-like
mechanism is `approvals.smart_policy`, which appends free text to the
system prompt of the auxiliary guardian LLM used in the default
`smart` mode — a stochastic Approval-layer nudge, not a Decision-layer
rule, and unevaluatable offline.

An owner who wants "ask me before a production deploy" must therefore
choose between overshooting (a deny glob — the deploy can never run)
and undershooting (a `smart_policy` sentence the guardian may or may
not honour on any given run).

### Evidence refs

- `docs/catalogue/translations-draft/hermes.json` FP-002 (confidence
  low, measured: false): "Hermes Agent (Nous Research) has no
  deploy-specific rule type and no user-authored 'ask' list: the only
  deterministic owner-authored terminal rule is approvals.deny
  (forbidden)."
- `adapters/hermes-assessment.md` §(b)(2)–(4): `approvals.deny`
  semantics; approval modes (`smart` default / `manual` / `off`);
  `smart_policy` "further appends owner text to that LLM's system
  prompt."
- Vendor docs (retrieved 2026-10-22): Security + Configuration pages —
  no `approvals.ask` / prompt-rule key exists anywhere in the
  documented `approvals.*` surface.

### Proposed change (sketch)

Add an owner-authored prompt rule list, evaluated at the same pipeline
stage as `approvals.deny` (after the hardline blocklist, before the
allowlist and before mode dispatch), with identical matching
semantics (case-insensitive fnmatch over the whole command text and
extracted executable candidates, launcher unwrapping, recursive
`shell -c` inspection):

```yaml
# ~/.hermes/config.yaml
approvals:
  mode: manual        # ask rules require a surface that can ask;
                      # see headless note below
  ask:
    - "deployctl release *production*"
    - "kubectl apply *--namespace=prod*"
```

Semantics to specify in the patch:

- A match forces the standard approval dialog
  (`[o]nce | [s]ession | [a]lways | [d]eny`) regardless of the
  dangerous-pattern table, in both `manual` and `smart` modes (in
  `smart` mode an `ask` match bypasses the guardian and escalates
  directly — the owner has already decided this class needs a human).
- In `off` / `--yolo` mode, `ask` rules degrade to **deny** (never to
  silent execution): yolo means "don't ask me", and an owner rule that
  exists to force a human decision must not silently vanish. This
  mirrors the documented `approvals.deny` behaviour of applying
  "before `--yolo`, `/yolo`, and `mode: off` are consulted."
- In headless contexts (`cron_mode` / `single_query_mode` /
  `unattended_mode`, each defaulting to `deny`), an `ask` match is
  governed by that context's key: under the default `deny` the command
  is blocked; under `approve` it runs. No new context key is needed.
- Deny still wins over ask when both match (deny is evaluated first;
  see FP-014).

Diff sketch (against `tools/approval.py`, names indicative — the live
checkout's actual symbols govern):

```diff
 @dataclass
 class ApprovalConfig:
     deny: list[str] = field(default_factory=list)
+    ask: list[str] = field(default_factory=list)
     ...
 
 def check_command(command, config, context):
     if matches_hardline(command):
         return Decision.FORBIDDEN("hardline blocklist")
     if matches_any(command, config.deny):
         return Decision.FORBIDDEN("approvals.deny")
+    if matches_any(command, config.ask):
+        if context.mode == "off":
+            return Decision.FORBIDDEN("approvals.ask under yolo/off")
+        return Decision.PROMPT("approvals.ask")
     ...
```

Config-schema and docs changes ride along: `hermes config check`
accepts `approvals.ask`; the Security page gains an "Owner prompt
rules" subsection next to the `approvals.deny` section, stating the
stage order and the yolo/headless degradations above.

### Acceptance probes

1. With `ask: ["deployctl release *production*"]` and
   `mode: manual`, `deployctl release production` in an interactive
   CLI session shows the approval dialog even though no
   dangerous-pattern row matches it; `deployctl release staging`
   shows no dialog.
2. Same config, `mode: smart`: the production command escalates to the
   dialog without a guardian verdict in the session log.
3. Same config, `--yolo`: the production command is blocked with the
   `approvals.ask` reason; it does not execute.
4. Same config, one-shot (`hermes chat --oneshot`) with default
   `single_query_mode: deny`: the production command is blocked; with
   `single_query_mode: approve` it runs.
5. A command matching both an `ask` glob and a `deny` glob is blocked
   (deny), and the recorded reason names the deny rule.

---

## FP-006 — Installer commands are unflagged; no registry/scope concept

### Problem

Invariants of the form *"prompt before `<installer> install`, and only
from `<registry_scope>`"* have no deterministic expression in Hermes,
in two independent halves:

1. **No prompt form.** Package installs (`pip install`, `npm install`,
   `cargo add`, …) appear nowhere in the documented dangerous-pattern
   trigger table, so they run unflagged by default. As with FP-002 the
   strongest owner binding is `approvals.deny` (`deny: ["pip install *"]`),
   which forbids where the invariant asked for a prompt.
2. **No scope slot at all.** Hermes' approval surface has no registry /
   scope / index concept: there is no config key, pattern variable, or
   hook point at which "which registry this install resolves against"
   is visible to the Decision layer. Even a deny glob can only match
   the literal command text (`--index-url …` when the user typed one);
   the effective registry chosen by the installer's own config files
   (`pip.conf`, `.npmrc`, `Cargo.toml` registries) is never part of the
   matched string.

### Evidence refs

- `docs/catalogue/translations-draft/hermes.json` FP-006 (confidence
  low, measured: false): "Hermes Agent (Nous Research) has no
  installer-specific gate and package installs are not in the
  documented dangerous-pattern trigger table, so '<installer> install'
  runs unflagged by default; the <registry_scope> slot has no
  corresponding mechanism at all."
- `adapters/hermes-assessment.md` §(b)(3): the ~40-row trigger table
  contains no install row.
- `adapters/hermes-assessment.md`, Decision surface: no-match on
  local/ssh backends "executes without a prompt."

### Proposed change (sketch)

Two parts; part 1 depends on the FP-002 mechanism, part 2 is
independent.

**Part 1 — prompt for installs.** Ship vendor trigger-table rows for
the common installer verbs so `manual` mode prompts and `smart` mode
consults the guardian, and document the `approvals.ask` form (FP-002)
as the owner-deterministic route:

```
# trigger-table additions (tools/approval.py DANGEROUS_PATTERNS)
(r"\b(pip|pip3|uv pip|npm|pnpm|yarn|bun)\s+(install|add)\b", "package install")
(r"\b(cargo|gem|composer|go)\s+(add|install|get)\b",          "package install")
(r"\bbrew\s+install\b",                                       "package install")
```

**Part 2 — make scope matchable.** Extend candidate extraction for
installer commands: when a matched command is an installer invocation,
resolve the effective registry from the installer's own config
(environment `PIP_INDEX_URL` / `npm_config_registry`, project
`pip.conf` / `.npmrc` in the command's cwd) and expose it to deny/ask
matching as a synthetic candidate string, e.g.
`__registry__ https://pypi.org/simple`. Owners can then write
scope rules as ordinary globs:

```yaml
approvals:
  deny:
    - "*__registry__ https://untrusted.example/*"   # illustrative
```

If part 2 is judged out of scope for the approval layer, the minimum
honest fix is documentary: the Security page should state explicitly
that install scope is not governed by the approval surface, so owners
do not mistake a command-text glob for a registry control.

### Acceptance probes

1. Clean config, `mode: manual`: `pip install requests` in the sandbox
   prompts (part 1) instead of running unflagged.
2. With the FP-002 ask rule `ask: ["pip install *"]` and no trigger
   row, the same command still prompts (owner route independent of
   the vendor table).
3. With `PIP_INDEX_URL=https://untrusted.example/simple` in the
   environment and a deny glob matching that registry candidate,
   `pip install requests` is blocked and the reason names the
   registry candidate (part 2); with the default index it is not
   blocked by that glob.
4. `pip download requests` (no install verb) is unaffected by the new
   trigger rows.

---

## FP-005 — No egress-allowlist mechanism for terminal fetch tools

### Problem

The invariant *"terminal egress (`curl` / `wget` / …) only to
`<approved_hosts>`; approval otherwise"* cannot be expressed in
Hermes. What exists is three partial, inverse, or differently-scoped
mechanisms:

1. `security.website_blocklist` — a **denylist** (exact / wildcard-
   subdomain / TLD-wildcard domains) that applies to the **web tools**
   (`web_search` / `web_extract` / browser), not to terminal
   `curl`/`wget`. An allowlist cannot be built by enumerating every
   unapproved host.
2. The always-on SSRF / private-address guard — blocks private,
   loopback, link-local and cloud-metadata destinations for
   URL-capable tools. That governs one address class ("untrusted by
   address"), not owner approval, and does not cover arbitrary public
   hosts.
3. Per-host `approvals.deny` globs (`*curl*<host>*`) — forbid named
   hosts one at a time; again a denylist, and trivially rephrased
   around (a different fetch binary, an IP literal, a redirect).

The result: an owner can block known-bad destinations but cannot
state the policy they actually mean — "these hosts are approved;
everything else asks."

### Evidence refs

- `docs/catalogue/translations-draft/hermes.json` FP-005 (confidence
  low, measured: false): "there is no rule kind that says '<fetch_bins>
  may only reach <approved_hosts>' — approvals.deny is a denylist of
  fnmatch globs, and an allowlist cannot be expressed by enumerating
  every unapproved host."
- `adapters/hermes-assessment.md`, Decision surface ("Also
  documented"): website blocklist scope (web/browser tools) and the
  SSRF guard, both vendor-owned; no terminal-egress allowlist appears
  anywhere in the documented `security.*` / `terminal.*` surface.
- `adapters/hermes.manifest.json`, `policy_ingestion.surface`: the
  full config surface lists `security { website_blocklist,
  allow_private_urls }` — no allowlist key.

### Proposed change (sketch)

Add a terminal-egress allowlist evaluated inside the approval
pipeline for commands whose executable candidate is a known fetch
binary (`curl`, `wget`, `aria2c`, `http`/`https` (HTTPie), `xh`):

```yaml
# ~/.hermes/config.yaml
security:
  terminal_egress:
    allow_hosts:
      - "api.example.com"
      - "*.artifacts.example.com"
    # on_unlisted: prompt (default) | deny
    on_unlisted: prompt
```

Semantics to specify:

- URL extraction reuses the existing candidate/normalization machinery
  (quote-aware parsing, launcher unwrapping, `shell -c` recursion);
  every literal URL host in the command is checked. All hosts listed →
  no egress prompt (the command proceeds to the normal pattern
  stages). Any unlisted host → `on_unlisted` outcome: `prompt` routes
  into the standard approval flow (manual: dialog; smart: guardian
  with the unlisted host named in its context); `deny` blocks with a
  reason naming the host.
- Redirects and resolved IPs are explicitly **out of scope** for the
  command-text layer and must be documented as such (a listed host
  can redirect to an unlisted one; only a network-layer control —
  e.g. the documented egress-proxy surface — can close that). The
  patch must not claim more than command-text governance.
- IP-literal and non-URL fetch forms (`curl 203.0.113.10`, `wget -qO-
  $URL`) follow the vendor's existing normalization limits: literal
  IPs are checked against the list as hosts; unresolvable variable
  forms fall through to the normal stages and are documented as a
  residual gap, not silently treated as approved.
- The SSRF/private-address guard continues to apply underneath: an
  allowlist entry never whitelists a private/metadata address unless
  `security.allow_private_urls` is also set.

Docs change: Security page gains a "Terminal egress allowlist"
subsection beside the website-blocklist section, including the
redirect limitation above in the same wording as the patch.

### Acceptance probes

1. `allow_hosts: ["api.example.com"]`, `mode: manual`:
   `curl https://api.example.com/v1/models` runs with no egress
   prompt; `curl https://other.example.net/` prompts, and the dialog
   / log names `other.example.net` as the unlisted host.
2. Same config with `on_unlisted: deny`: the second command is blocked
   outright; the recorded reason names the host.
3. `curl https://api.example.com@other.example.net/` (userinfo trick)
   is judged on `other.example.net`, not on the userinfo text.
4. `curl http://169.254.169.254/latest/meta-data/` remains blocked by
   the SSRF guard even if `169.254.169.254` is (mis)added to
   `allow_hosts` without `allow_private_urls`.
5. Web-tool behaviour is unchanged: `website_blocklist` still governs
   `web_extract` independently of `terminal_egress`.

---

## FP-014 — Precedence across rule kinds is undocumented

### Problem

Hermes documents a **stage order** but not a **precedence rule**. The
docs fix: (1) the hardline blocklist trips before the approval layer
and cannot be overridden, including by "allow always"; (2)
`approvals.deny` blocks unconditionally, consulted before `--yolo`,
`/yolo`, or `mode: off`. They do **not** state the outcome of the
overlap an owner will hit first in practice:

> A command matches an `approvals.deny` glob **and** a
> `command_allowlist` entry (exact text, glob, or a dangerous-pattern
> rule key persisted by a past "always" answer). Which wins?

The deny language ("unconditionally / before … consulted") suggests
deny, but no page states it, and the allowlist has its own strong
documented behaviour in the other direction: rule keys are "honored
even on unattended surfaces" under `deny` context modes. Two
documented "wins even when you'd expect otherwise" claims, no stated
resolution when they collide. An adapter (or an owner) that encodes
most-restrictive-wins here is encoding an inference as engine fact.

The same gap applies pairwise to session approvals vs deny (is a
command approved earlier in the session re-checked against a deny
rule added mid-session, given deny changes "take effect immediately"
via the mtime-keyed config cache?) and to the FP-002 `ask` proposal if
adopted.

### Evidence refs

- `docs/catalogue/translations-draft/hermes.json` FP-014 (confidence
  low, measured: false): "Hermes Agent (Nous Research) does not
  document a general most-restrictive-wins precedence rule, and this
  translation must not assert one. … One overlap is explicitly
  UNRESOLVED in the docs."
- `adapters/hermes-assessment.md` §(b) ceiling 7 ("Precedence is only
  partially ordered in the docs") and Open questions #3 ("Deny-vs-
  allowlist precedence … *Would resolve:* vendor documentation of the
  stage order, or a live A3/A4 probe behind the LIVE-UNLOCK").
- `adapters/hermes.manifest.json`, `open_questions`: same unresolved
  pair recorded.

### Proposed change (sketch)

This is primarily a **documentation + test** fix; the code change is
only whatever the documented rule turns out to require.

1. **Docs:** add a "Precedence" subsection to the Security page
   stating the complete stage order as a single ordered list —
   parse floor → hardline → `approvals.deny` → (proposed
   `approvals.ask`) → allowlist / session approvals → mode dispatch
   (manual prompt / smart guardian / off) → no-match execution —
   and, for each adjacent pair, the winner when both match. State the
   deny-vs-allowlist outcome in one unambiguous sentence, e.g.:

   > "If a command matches both an `approvals.deny` glob and a
   > `command_allowlist` entry, the deny glob wins: the command is
   > blocked. An 'always' answer never overrides a deny rule, and
   > adding a deny rule blocks commands that were previously
   > allowlisted, in the current session and future sessions."

   (If the implemented behaviour is the opposite, document that
   instead — the fix is that the behaviour is *stated and tested*,
   not that it takes a particular side. The sentence above is the
   recommended semantics: it matches the existing "unconditionally"
   language and is the only reading under which a deny rule is a
   reliable emergency brake on a stale allowlist entry.)

2. **Code (if needed to match the documented rule):** ensure the
   pipeline evaluates deny before the allowlist lookup, including
   the rule-key path used on unattended surfaces, and that a
   mid-session deny edit (mtime cache refresh) is honoured for
   already-session-approved pattern classes.

3. **Tests:** land the acceptance probes below as regression tests in
   the Hermes test suite so the precedence cannot silently flip in a
   later release (the surface has documented churn — e.g. the Tirith
   scanner removal noted in the assessment).

### Acceptance probes

1. Config: `deny: ["rm -rf *"]`, `command_allowlist: ["rm -rf *"]`
   (exact-text collision). `rm -rf <throwaway>` in an interactive
   session: outcome is the documented winner, and the session log /
   error names the winning rule kind.
2. Same collision via a rule key: allowlist contains the
   dangerous-pattern key for recursive delete; the deny glob above
   still decides per the documented rule.
3. Temporal probe: approve `rm -rf <a>` with "always" (allowlist
   entry written); then add `deny: ["rm -rf *"]` to the config;
   `rm -rf <b>` in a **new** session and in the **same** session both
   follow the documented rule.
4. Unattended surface: with `unattended_mode: deny` and a rule-key
   allowlist entry matching a flagged command, plus a deny glob
   matching the same command, the outcome follows the documented
   rule (this is the pair where both sides have "wins anyway"
   language today).
5. `hermes approvals suggest` never proposes re-allowlisting a
   command class that a current deny glob matches.

---

## Live-observed gaps

*This section is completed from the Stage 2 live run
(`evidence/live-campaign-2026-10-23/hermes/RESULTS.md`). Entries are
added only for behaviour actually observed live; DOC-only expectations
stay in the entries above and are not duplicated here as findings.*

## Live-observed gaps (Hermes v0.22.5, campaign 2026-10-23)

Evidence: `evidence/live-campaign-2026-10-23/hermes/` (RESULTS.md, runs.json,
sessions/, incl. `state.db`).

1. **FP-014 is resolvable, and the answer matters.** In v0.22.5 source
   (`tools/approval.py::check_all_command_guards`) the permanent allowlist is
   consulted **after** the deny stage — deny beats allowlist. Live confirmation
   of the neighbouring semantics: an "always" answer persisted the **pattern
   rule key** (`command_allowlist: ["delete in root path"]`), so one approval
   silently authorizes every future command in that pattern class, across
   sessions, with no per-command trace in the tool result. The docs fix in
   FP-014 should also state the allowlist grain (pattern key, not literal
   command) — it is the single most consequential approval fact in the product.
2. **Deny globs are literal, not semantic (sharpens FP-014/FP-002 acceptance).**
   With `approvals.deny: ["rm -rf *"]`, the `rm -rf …` form was blocked with the
   rule named and no dialog, while `rm --recursive --force …` fell through to
   the pattern-table ask. An owner who writes the obvious glob leaves the
   long-flag spelling ungoverned by the deny stage. Acceptance probe: a deny
   rule expressed once should be tested against flag-spelling variants.
3. **LT-09 live: no stage exists for deploy-class commands (FP-002).**
   `deployctl release production` produced no ask, no block, no rule hook —
   the tool simply attempted execution (exit 127, binary absent). The FP-002
   `approvals.ask` proposal remains the missing expression.
4. **Dialog form drifted from the docs.** The shipped dialog is a numbered
   select panel (1 Allow once / 2 session / 3 permanent allowlist / 4 Deny /
   5 Show full command) with a live countdown, not the `[o]nce`-style letter
   dialog the docs describe. Any operator automation or training material
   written against the documented dialog will mis-answer the real one.
5. **Env-snapshot persistence (new, minor).** The terminal tool's shell-env
   snapshot cache (`~/.hermes/cache/scratch/hermes-snap-*.sh`) persists the
   agent process environment verbatim — including provider key env vars named
   by `model.key_env`. Keys supplied env-only (never written to `.env` by the
   operator) still land on disk in the cache. Proposed fix: exclude env vars
   referenced by `model.key_env` (and `*_API_KEY`-shaped names) from snapshot
   files, or store snapshots with 0600 + a documented lifetime. (Observed
   during the campaign's secret-persistence scan; the four files were deleted
   and a re-scan came back clean.)
