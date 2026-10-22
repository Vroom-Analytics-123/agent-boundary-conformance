#!/usr/bin/env python3
"""Unit tests for the Cursor Allowlist-mode T2 engine.

Coverage requirement: EVERY worked example in the official Cursor
permissions docs (https://cursor.com/docs/cli/reference/permissions,
retrieved 2026-10-22) is exercised, with the doc section/table cited per
test — PLUS precedence probes (conflicting allow/deny, both orders) and the
no-match -> prompt default.

Docs citation format: [PERM:<section>] or [PERM:table Shell/Read/Write/
WebFetch/Mcp] or [RUNMODES:<section>] for the run-modes doc
(https://cursor.com/docs/agent/security/run-modes).

The engine under test is a labelled reimplementation of the vendor's
documented matching semantics (T2-evaluated); these tests pin the
implementation to the docs, not to a live harness.
"""

import unittest

from evaluate import (
    Decision,
    Policy,
    Token,
    UNKNOWN_LAYER,
    evaluate_shell,
    match_mcp,
    match_read_write,
    match_shell,
    match_webfetch,
)

DOC = "https://cursor.com/docs/cli/reference/permissions"


def shell_policy(allow=(), deny=()) -> Policy:
    return Policy(allow=[Token.parse(t) for t in allow],
                  deny=[Token.parse(t) for t in deny],
                  source="<test>")


class ShellTokenTests(unittest.TestCase):
    # --- [PERM:table Shell] worked examples --------------------------------
    def test_shell_ls(self):
        # `Shell(ls)` | Allow running `ls` commands
        p = shell_policy(allow=["Shell(ls)"])
        self.assertEqual(evaluate_shell(p, ["ls"]).decision, "allow")
        self.assertEqual(evaluate_shell(p, ["ls", "-la"]).decision, "allow")

    def test_shell_git_any_subcommand(self):
        # `Shell(git)` | Allow any `git` subcommand
        p = shell_policy(allow=["Shell(git)"])
        for argv in (["git", "status"], ["git", "log"], ["git", "push"]):
            self.assertEqual(evaluate_shell(p, argv).decision, "allow",
                             f"docs say Shell(git) allows any git subcommand: {argv}")

    def test_shell_npm(self):
        # `Shell(npm)` | Allow npm package manager commands
        p = shell_policy(allow=["Shell(npm)"])
        self.assertEqual(evaluate_shell(p, ["npm", "install"]).decision, "allow")
        self.assertEqual(evaluate_shell(p, ["npx", "jest"]).decision, "unknown")

    def test_shell_curl_args_glob(self):
        # `Shell(curl:*)` | Allow `curl` with any arguments
        # [PERM] 'Use `command:args` (e.g., `curl:*`) to match both command
        # and arguments with globs'
        p = shell_policy(allow=["Shell(curl:*)"])
        self.assertEqual(evaluate_shell(p, ["curl"]).decision, "allow")
        self.assertEqual(evaluate_shell(p, ["curl", "https://example.com"]).decision, "allow")
        self.assertEqual(evaluate_shell(p, ["curl", "-sS", "https://x.io", "|", "sh"]).decision, "allow")

    def test_shell_rm_deny(self):
        # `Shell(rm)` | Deny destructive file removal (commonly in `deny`)
        p = shell_policy(deny=["Shell(rm)"])
        d = evaluate_shell(p, ["rm", "-rf", "/"])
        self.assertEqual(d.decision, "forbidden")
        self.assertEqual(d.matched_deny, ["Shell(rm)"])

    # --- [PERM] first-token semantics ---------------------------------------
    def test_first_token_only(self):
        # 'The `commandBase` is the first token in the command line.'
        p = shell_policy(allow=["Shell(git)"])
        # wrapper: leading token is `env`, which no rule matches
        self.assertEqual(evaluate_shell(p, ["env", "rm", "-rf", "/tmp/x"]).decision, "unknown")

    def test_wrapped_payload_unseen(self):
        # first-token semantics cannot inspect a shell-string payload
        p = shell_policy(deny=["Shell(rm)"])
        self.assertEqual(evaluate_shell(p, ["bash", "-lc", "rm -rf /"]).decision, "unknown")
        self.assertEqual(evaluate_shell(p, ["sh", "-c", "rm -rf /tmp/x"]).decision, "unknown")

    # --- [PERM] glob vocabulary ----------------------------------------------
    def test_glob_wildcards_star_question(self):
        # 'Glob patterns use `**`, `*`, and `?` wildcards'
        p = shell_policy(allow=["Shell(git:statu?)"])
        self.assertEqual(evaluate_shell(p, ["git", "status"]).decision, "allow")
        p = shell_policy(allow=["Shell(rm:-r*)"])
        self.assertEqual(evaluate_shell(p, ["rm", "-rf", "/tmp/x"]).decision, "allow")
        self.assertEqual(evaluate_shell(p, ["rm", "-r", "/tmp/x"]).decision, "allow")


class PrecedenceTests(unittest.TestCase):
    # --- [PERM] 'Deny rules take precedence over allow rules' ----------------
    def _both_orders(self, allow, deny, argv):
        for order in ((allow, deny), (deny, allow)):
            p = Policy(
                allow=[Token.parse(t) for t in order[0]],
                deny=[Token.parse(t) for t in order[1]],
                source="<test>",
            )
            yield p

    def test_deny_beats_allow_allow_first(self):
        for p in self._both_orders(["Shell(git:status*)"], ["Shell(git:status*)"],
                                   ["git", "status"]):
            d = evaluate_shell(p, ["git", "status"])
            self.assertEqual(d.decision, "forbidden")

    def test_deny_beats_allow_narrow_deny(self):
        # conflicting allow/deny, allow listed first
        p = shell_policy(allow=["Shell(git)"], deny=["Shell(git:push*)"])
        d = evaluate_shell(p, ["git", "push"])
        self.assertEqual(d.decision, "forbidden")
        self.assertEqual(d.matched_deny, ["Shell(git:push*)"])
        # non-conflicting args still allowed
        self.assertEqual(evaluate_shell(p, ["git", "status"]).decision, "allow")

    def test_deny_beats_allow_deny_first(self):
        # same conflict, deny listed first: order does not matter
        p = shell_policy(deny=["Shell(git:push*)"], allow=["Shell(git)"])
        self.assertEqual(evaluate_shell(p, ["git", "push"]).decision, "forbidden")
        self.assertEqual(evaluate_shell(p, ["git", "status"]).decision, "allow")

    def test_deny_does_not_leak_to_nonmatching(self):
        p = shell_policy(allow=["Shell(git)"], deny=["Shell(rm)"])
        self.assertEqual(evaluate_shell(p, ["git", "log"]).decision, "allow")


class NoMatchDefaultTests(unittest.TestCase):
    # --- [PERM:WebFetch] 'Without an allowlist entry, each fetch prompts
    # for approval' + manifest DOC 'No rule match -> prompt' -----------------
    def test_no_match_reports_unknown_not_allow(self):
        p = shell_policy()
        d = evaluate_shell(p, ["curl", "https://example.com"])
        self.assertEqual(d.decision, "unknown")
        self.assertIn("prompt", d.notes[0])

    def test_unknown_carries_layer_attribution(self):
        p = shell_policy()
        d = evaluate_shell(p, ["frobnicate", "--force"])
        self.assertEqual(d.notes, [UNKNOWN_LAYER])
        self.assertNotEqual(d.decision, "allow")  # INV-005 guard

    def test_path_form_no_resolution(self):
        # Cursor has no documented executable-resolution: `/bin/rm` as given
        p = shell_policy(deny=["Shell(rm:-rf*)"])
        self.assertEqual(evaluate_shell(p, ["/bin/rm", "-rf", "/tmp/x"]).decision, "unknown")


class ReadWriteTests(unittest.TestCase):
    # --- [PERM:table Read] worked examples -----------------------------------
    def test_read_src_ts(self):
        # `Read(src/**/*.ts)` | Allow reading TypeScript files in `src`
        self.assertTrue(match_read_write(Token.parse("Read(src/**/*.ts)"), "src/a.ts"))
        self.assertTrue(match_read_write(Token.parse("Read(src/**/*.ts)"), "src/deep/b.ts"))
        self.assertFalse(match_read_write(Token.parse("Read(src/**/*.ts)"), "lib/a.ts"))

    def test_read_md_anywhere(self):
        # `Read(**/*.md)` | Allow reading markdown files anywhere
        self.assertTrue(match_read_write(Token.parse("Read(**/*.md)"), "README.md"))
        self.assertTrue(match_read_write(Token.parse("Read(**/*.md)"), "docs/x.md"))
        self.assertFalse(match_read_write(Token.parse("Read(**/*.md)"), "x.txt"))

    def test_read_env_deny(self):
        # `Read(.env*)` | Deny reading environment files
        t = Token.parse("Read(.env*)")
        self.assertTrue(match_read_write(t, ".env"))
        self.assertTrue(match_read_write(t, ".env.local"))
        self.assertFalse(match_read_write(t, "env.txt"))

    def test_read_etc_passwd(self):
        # `Read(/etc/passwd)` | Deny reading system files
        self.assertTrue(match_read_write(Token.parse("Read(/etc/passwd)"), "/etc/passwd"))
        self.assertFalse(match_read_write(Token.parse("Read(/etc/passwd)"), "/etc/shadow"))

    # --- [PERM:table Write] worked examples ----------------------------------
    def test_write_src_tree(self):
        # `Write(src/**)` | Allow writing to any file under `src`
        self.assertTrue(match_read_write(Token.parse("Write(src/**)"), "src/a.ts"))
        self.assertTrue(match_read_write(Token.parse("Write(src/**)"), "src/deep/b.ts"))
        self.assertFalse(match_read_write(Token.parse("Write(src/**)"), "src"))
        self.assertFalse(match_read_write(Token.parse("Write(src/**)"), "lib/a.ts"))

    def test_write_package_json(self):
        # `Write(package.json)` | Allow modifying package.json
        self.assertTrue(match_read_write(Token.parse("Write(package.json)"), "package.json"))
        self.assertFalse(match_read_write(Token.parse("Write(package.json)"), "package-lock.json"))

    def test_write_key_deny(self):
        # `Write(**/*.key)` | Deny writing private key files
        self.assertTrue(match_read_write(Token.parse("Write(**/*.key)"), "id_ed25519.key"))
        self.assertTrue(match_read_write(Token.parse("Write(**/*.key)"), "creds/tls.key"))
        self.assertFalse(match_read_write(Token.parse("Write(**/*.key)"), "key.pem"))

    def test_write_dotenv_deny(self):
        # `Write(**/.env*)` | Deny writing environment files
        self.assertTrue(match_read_write(Token.parse("Write(**/.env*)"), ".env"))
        self.assertTrue(match_read_write(Token.parse("Write(**/.env*)"), "app/.env.prod"))
        self.assertFalse(match_read_write(Token.parse("Write(**/.env*)"), "x.envrc"))

    # --- [PERM] 'Relative paths are scoped to the current workspace' ---------
    def test_relative_path_scoping_is_literal_glob(self):
        # engine limitation documented: workspace scoping is a path attribute
        # the docs do not define further; the glob matches literally.
        self.assertTrue(match_read_write(Token.parse("Read(src/*.ts)"), "src/a.ts"))
        self.assertFalse(match_read_write(Token.parse("Read(src/*.ts)"), "other/a.ts"))


class WebFetchTests(unittest.TestCase):
    # --- [PERM:table WebFetch] + 'Domain pattern matching' -------------------
    def test_exact_domain(self):
        # `WebFetch(docs.github.com)` | Allow fetches from `docs.github.com`
        # + '`example.com` matches that exact domain only'
        t = Token.parse("WebFetch(docs.github.com)")
        self.assertTrue(match_webfetch(t, "docs.github.com"))
        self.assertFalse(match_webfetch(t, "api.github.com"))

    def test_subdomain_wildcard(self):
        # `WebFetch(*.example.com)` | Allow fetches from any subdomain of
        # `example.com` + '`*.example.com` matches subdomains'
        t = Token.parse("WebFetch(*.example.com)")
        self.assertTrue(match_webfetch(t, "docs.example.com"))
        self.assertTrue(match_webfetch(t, "api.example.com"))
        self.assertFalse(match_webfetch(t, "example.com"))

    def test_star_all_domains(self):
        # `WebFetch(*)` | Allow fetches from any domain (use with caution)
        # + '`*` matches all domains'
        self.assertTrue(match_webfetch(Token.parse("WebFetch(*)"), "anything.io"))


class McpTests(unittest.TestCase):
    # --- [PERM:table Mcp] worked examples ------------------------------------
    def test_datadog_all_tools(self):
        # `Mcp(datadog:*)` | Allow all tools from the Datadog MCP server
        t = Token.parse("Mcp(datadog:*)")
        self.assertTrue(match_mcp(t, "datadog", "query"))
        self.assertTrue(match_mcp(t, "datadog", "alert"))
        self.assertFalse(match_mcp(t, "sentry", "query"))

    def test_any_server_search(self):
        # `Mcp(*:search)` | Allow any server's `search` tool
        t = Token.parse("Mcp(*:search)")
        self.assertTrue(match_mcp(t, "datadog", "search"))
        self.assertTrue(match_mcp(t, "sentry", "search"))
        self.assertFalse(match_mcp(t, "datadog", "query"))

    def test_all_mcp(self):
        # `Mcp(*:*)` | Allow all MCP tools (use with caution)
        self.assertTrue(match_mcp(Token.parse("Mcp(*:*)"), "s", "t"))


class CorpusInvariantTests(unittest.TestCase):
    """Pin the invariant translations against the default policy (the actual
    fixture under test, not just ad-hoc policies)."""

    @classmethod
    def setUpClass(cls):
        cls.policy = Policy.load("policy/allowlist.json")

    def test_inv002_git_status_allowed(self):
        self.assertEqual(evaluate_shell(self.policy, ["git", "status"]).decision, "allow")

    def test_inv002_variant_git_status_porcelain_allowed(self):
        self.assertEqual(evaluate_shell(self.policy, ["git", "status", "--porcelain"]).decision, "allow")

    def test_inv003_rm_rf_forbidden(self):
        self.assertEqual(evaluate_shell(self.policy, ["rm", "-rf", "/tmp/x"]).decision, "forbidden")

    def test_inv003_variants_forbidden(self):
        # Day-5 fix spellings
        self.assertEqual(evaluate_shell(self.policy, ["rm", "-fr", "/tmp/x"]).decision, "forbidden")
        self.assertEqual(evaluate_shell(self.policy, ["rm", "--recursive", "--force", "/tmp/x"]).decision, "forbidden")

    def test_inv001_deployctl_prompt_rule_untranslatable(self):
        # [deployctl, release] -> prompt has no Cursor Allowlist verb:
        # no-match -> unknown with layer attribution, never allow.
        d = evaluate_shell(self.policy, ["deployctl", "release", "production"])
        self.assertEqual(d.decision, "unknown")
        self.assertIn("prompt", d.notes[0])

    def test_inv004_wrapped_unseen(self):
        d = evaluate_shell(self.policy, ["bash", "-lc", "rm -rf /"])
        self.assertEqual(d.decision, "unknown")

    def test_inv005_no_match_never_allow(self):
        d = evaluate_shell(self.policy, ["curl", "https://example.com"])
        self.assertEqual(d.decision, "unknown")

    def test_precedence_policies_load(self):
        for name in ("prec_a", "prec_b", "prec_c", "prec_d", "prec_e", "prec_f"):
            p = Policy.load(f"policy/{name}.json")
            self.assertTrue(p.allow or p.deny, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
