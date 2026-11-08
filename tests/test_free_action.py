"""Tests for the free GitHub Action + example workflow (static validation).

No network, no runner: these tests parse the YAML the Action ships and
assert the contract the Action promises — it runs the CLI, fails the
build on BLOCKED (exit 2 is never swallowed), uploads the evidence
bundle as a CI artifact, and posts a verdict summary on the PR.

Stdlib + PyYAML (already used by the local test env).
"""

import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / "action.yml"
WORKFLOW = REPO / ".github" / "workflows" / "fineprint-check.yml"
WIRING = REPO / "docs" / "FREE_CHECK_ACTION.md"


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text())


class TestAction(unittest.TestCase):
    def test_action_yml_parses_and_names_inputs(self):
        doc = load_yaml(ACTION)
        self.assertIn("name", doc)
        self.assertIn("description", doc)
        self.assertIn("runs", doc)
        self.assertEqual(doc["runs"]["using"], "composite")
        inputs = doc["inputs"]
        for name in ("harness", "policy", "only", "baseline"):
            self.assertIn(name, inputs, f"missing input {name}")

    def test_action_runs_cli_and_uploads_bundle(self):
        doc = load_yaml(ACTION)
        text = Path(ACTION).read_text()
        # The check step invokes the CLI as: python3
        # "${GITHUB_ACTION_PATH}/fineprint" check ...
        self.assertIn('"${GITHUB_ACTION_PATH}/fineprint" check', text)
        self.assertIn("actions/upload-artifact", text)
        self.assertIn("bundle.json", text)

    def test_action_never_swallows_blocked(self):
        # A step that swallows the CLI's exit 2 would silently pass a
        # BLOCKED run. No `|| true`, no `continue-on-error: true` on the
        # check step.
        text = Path(ACTION).read_text()
        self.assertNotIn("|| true", text)
        doc = load_yaml(ACTION)
        for step in doc["runs"]["steps"]:
            if "fineprint check" in str(step.get("run", "")):
                self.assertNotEqual(
                    str(step.get("continue-on-error", "")).lower(), "true")

    def test_action_inputs_all_optional(self):
        # Point-and-click: every input must be optional so the workflow
        # can call the action with no `with:` block at all.
        doc = load_yaml(ACTION)
        for name, spec in doc["inputs"].items():
            self.assertNotEqual(
                str((spec or {}).get("required", "")).lower(), "true",
                f"input {name} must be optional")

    def test_action_posts_pr_summary(self):
        text = Path(ACTION).read_text()
        self.assertIn("pull_request", text)
        self.assertIn("scorecard.json", text)


class TestExampleWorkflow(unittest.TestCase):
    def test_workflow_parses_and_uses_local_action(self):
        doc = load_yaml(WORKFLOW)
        self.assertIn("jobs", doc)
        text = Path(WORKFLOW).read_text()
        self.assertIn("uses: ./", text)

    def test_workflow_has_claude_code_job_without_secrets(self):
        # The no-secrets path must exist: claude-code needs no binary,
        # no key, no network.
        doc = load_yaml(WORKFLOW)
        text = Path(WORKFLOW).read_text()
        self.assertIn("claude-code", text)
        jobs = doc["jobs"]
        self.assertTrue(any("claude" in name for name in jobs))

    def test_workflow_has_gate_step(self):
        text = Path(WORKFLOW).read_text()
        self.assertIn("gate check", text)

    def test_workflow_has_zero_config_job(self):
        # One workflow file, no config: at least one job calls the action
        # with no `with:` block.
        doc = load_yaml(WORKFLOW)
        found = False
        for job in doc["jobs"].values():
            for step in job.get("steps", []):
                uses = str(step.get("uses", ""))
                if "fineprint" in uses.lower() or uses.startswith("./"):
                    if not step.get("with"):
                        found = True
        self.assertTrue(found, "no zero-config action step in the workflow")

    def test_workflow_declares_pr_comment_permission(self):
        doc = load_yaml(WORKFLOW)
        perms = doc.get("permissions", {})
        self.assertEqual(perms.get("pull-requests"), "write")

    def test_wiring_guide_exists_and_covers_oracle_restore(self):
        self.assertTrue(WIRING.exists())
        text = WIRING.read_text()
        self.assertIn("action.yml", text)
        self.assertIn("VENDORED.md", text)
        self.assertIn("MUSE_HEADLESS_KEY", text)


if __name__ == "__main__":
    unittest.main()
