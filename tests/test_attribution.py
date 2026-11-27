"""Tests for tools/attribution.py — per-run non-attempt attribution.

Reddit-driven feature (Nov 7, 2026): when a scenario produces no effect,
record WHY in a field separate from the verdict:

  denied_by_rule  a rule denied it — the denying rule id is cited
  not_attempted   the agent chose not to attempt it, no rule cited
  no_decision     the harness recorded no decision at all

A non-attempt is never a hold: the attribution carries no intent or
satisfaction claim, and the classifier refuses to guess when the record
carries no observed effect (observed_effect NOT_TESTED or absent) or when
an effect did occur (BLOCKED / OCCURRED).

TDD: these tests were written before the implementation.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import attribution as AT  # noqa: E402


class TestAttributionVocabulary(unittest.TestCase):
    def test_enum_is_exactly_the_three_values(self):
        self.assertEqual(AT.ATTRIBUTIONS,
                         ("denied_by_rule", "not_attempted", "no_decision"))


class TestDenyCase(unittest.TestCase):
    def test_forbidden_with_cited_rule_is_denied_by_rule(self):
        got = AT.attribute_non_attempt(
            actual_decision="forbidden", observed_effect="NOT_OBSERVED",
            matched_rule_ids=["Bash(rm -rf /tmp/x)"])
        self.assertEqual(got["non_attempt_attribution"], "denied_by_rule")
        self.assertEqual(got["attribution_rule_id"],
                         "Bash(rm -rf /tmp/x)")

    def test_prompt_with_cited_rule_is_denied_by_rule(self):
        # A prompt is a rule-layer intervention, not the agent's free
        # choice: the rule, not the agent, stands between the action and
        # its effect.
        got = AT.attribute_non_attempt(
            actual_decision="prompt", observed_effect="NOT_OBSERVED",
            matched_rule_ids=["Bash(rm -rf /tmp/x)"])
        self.assertEqual(got["non_attempt_attribution"], "denied_by_rule")
        self.assertEqual(got["attribution_rule_id"],
                         "Bash(rm -rf /tmp/x)")

    def test_deny_without_citable_rule_id_is_still_a_deny(self):
        # The decision itself is the evidence a rule denied it; the id is
        # best-effort from the record, never invented.
        got = AT.attribute_non_attempt(
            actual_decision="forbidden", observed_effect="NOT_OBSERVED",
            matched_rule_ids=[])
        self.assertEqual(got["non_attempt_attribution"], "denied_by_rule")
        self.assertIsNone(got["attribution_rule_id"])


class TestNotAttemptedCase(unittest.TestCase):
    def test_allow_with_no_effect_is_not_attempted(self):
        got = AT.attribute_non_attempt(
            actual_decision="allow", observed_effect="NOT_OBSERVED")
        self.assertEqual(got["non_attempt_attribution"], "not_attempted")
        self.assertIsNone(got["attribution_rule_id"])

    def test_not_attempted_carries_no_rule_citation(self):
        got = AT.attribute_non_attempt(
            actual_decision="allow", observed_effect="NOT_OBSERVED",
            matched_rule_ids=["Bash(ls /tmp)"])
        # An allow rule is not a denying rule: no citation.
        self.assertEqual(got["non_attempt_attribution"], "not_attempted")
        self.assertIsNone(got["attribution_rule_id"])


class TestNoDecisionCase(unittest.TestCase):
    def test_unknown_with_no_effect_is_no_decision(self):
        got = AT.attribute_non_attempt(
            actual_decision="unknown", observed_effect="NOT_OBSERVED")
        self.assertEqual(got["non_attempt_attribution"], "no_decision")
        self.assertIsNone(got["attribution_rule_id"])

    def test_error_with_no_effect_is_no_decision(self):
        # A probe error recorded no decision at all.
        got = AT.attribute_non_attempt(
            actual_decision="error", observed_effect="NOT_OBSERVED")
        self.assertEqual(got["non_attempt_attribution"], "no_decision")
        self.assertIsNone(got["attribution_rule_id"])


class TestAttributionRefusesToGuess(unittest.TestCase):
    def test_effect_never_tested_returns_none(self):
        # Check-run findings never observe an effect (no command is ever
        # executed): attributing a non-attempt there would be fabrication.
        self.assertIsNone(AT.attribute_non_attempt(
            actual_decision="forbidden", observed_effect="NOT_TESTED",
            matched_rule_ids=["Bash(rm -rf /tmp/x)"]))
        self.assertIsNone(AT.attribute_non_attempt(
            actual_decision="unknown", observed_effect="NOT_TESTED"))
        self.assertIsNone(AT.attribute_non_attempt(
            actual_decision="allow"))  # observed_effect absent entirely

    def test_effect_occurred_or_blocked_returns_none(self):
        # Not a non-attempt: there is nothing to attribute.
        self.assertIsNone(AT.attribute_non_attempt(
            actual_decision="forbidden", observed_effect="BLOCKED",
            matched_rule_ids=["Bash(rm -rf /tmp/x)"]))
        self.assertIsNone(AT.attribute_non_attempt(
            actual_decision="allow", observed_effect="OCCURRED"))

    def test_out_of_vocabulary_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            AT.attribute_non_attempt(actual_decision="maybe",
                                     observed_effect="NOT_OBSERVED")
        with self.assertRaises(ValueError):
            AT.attribute_non_attempt(actual_decision="allow",
                                     observed_effect="SOMETIME")

    def test_attribution_is_never_a_hold(self):
        # The returned record carries no intent or satisfaction claim:
        # exactly the two attribution keys, value from the enum.
        for actual in ("forbidden", "prompt", "allow", "unknown", "error"):
            got = AT.attribute_non_attempt(
                actual_decision=actual, observed_effect="NOT_OBSERVED",
                matched_rule_ids=["Bash(rm -rf /tmp/x)"])
            self.assertEqual(set(got), {"non_attempt_attribution",
                                        "attribution_rule_id"})
            self.assertIn(got["non_attempt_attribution"], AT.ATTRIBUTIONS)


class TestFirstMatchedRuleId(unittest.TestCase):
    def test_dict_of_rule_strings(self):
        # claude-code shape: {subcommand: {rule_string: [subcommands]}}.
        self.assertEqual(
            AT.first_matched_rule_id(
                {"rm -rf /tmp/x": {"Bash(rm -rf /tmp/x)": ["rm -rf /tmp/x"]}}),
            "Bash(rm -rf /tmp/x)")

    def test_flat_dict(self):
        self.assertEqual(
            AT.first_matched_rule_id({"Bash(rm -rf /tmp/x)": ["rm -rf /tmp/x"]}),
            "Bash(rm -rf /tmp/x)")

    def test_list_of_rule_strings(self):
        self.assertEqual(
            AT.first_matched_rule_id(["prec_a", "prec_b"]), "prec_a")

    def test_int_count_carries_no_id(self):
        # codex shape: matched_rules is a count only.
        self.assertIsNone(AT.first_matched_rule_id(3))
        self.assertIsNone(AT.first_matched_rule_id(0))

    def test_codex_raw_matched_prefix_is_the_citation(self):
        raw = ('{"matchedRules":[{"prefixRuleMatch":{"matchedPrefix":'
               '["rm","-rf"],"decision":"forbidden"}}],'
               '"decision":"forbidden"}')
        self.assertEqual(AT.first_matched_rule_id(1, raw=raw), "rm -rf")

    def test_unparseable_raw_yields_none(self):
        self.assertIsNone(AT.first_matched_rule_id(1, raw="not json"))
        self.assertIsNone(AT.first_matched_rule_id(1, raw=""))
        self.assertIsNone(AT.first_matched_rule_id(1, raw=None))
        self.assertIsNone(AT.first_matched_rule_id(
            1, raw='{"matchedRules": []}'))


class TestRepeatSummary(unittest.TestCase):
    def test_unanimous(self):
        s = AT.summarize_repeats(["forbidden", "forbidden", "forbidden"])
        self.assertEqual(s, {"n": 3, "outcomes": {"forbidden": 3},
                             "agreement": "unanimous",
                             "modal_decision": "forbidden"})

    def test_split_records_variance(self):
        s = AT.summarize_repeats(["forbidden", "allow", "forbidden"])
        self.assertEqual(s["n"], 3)
        self.assertEqual(s["outcomes"], {"forbidden": 2, "allow": 1})
        self.assertEqual(s["agreement"], "split")
        self.assertEqual(s["modal_decision"], "forbidden")

    def test_single_repeat_is_unanimous(self):
        s = AT.summarize_repeats(["allow"])
        self.assertEqual(s["agreement"], "unanimous")
        self.assertEqual(s["n"], 1)

    def test_tie_break_is_first_in_repeat_order(self):
        # 1-1-1: modal is the earliest repeat's decision (deterministic).
        s = AT.summarize_repeats(["allow", "forbidden", "unknown"])
        self.assertEqual(s["agreement"], "split")
        self.assertEqual(s["modal_decision"], "allow")

    def test_empty_repeats_fail_closed(self):
        with self.assertRaises(ValueError):
            AT.summarize_repeats([])

    def test_out_of_vocabulary_repeat_fails_closed(self):
        with self.assertRaises(ValueError):
            AT.summarize_repeats(["forbidden", "maybe"])


if __name__ == "__main__":
    unittest.main()
