from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class CiTopologyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.pages = (WORKFLOWS / "pages.yml").read_text(encoding="utf-8")

    def test_ci_avoids_feature_push_duplication_and_is_bounded(self) -> None:
        self.assertIn("pull_request:", self.ci)
        self.assertIn("branches: [main]", self.ci)
        self.assertIn('tags: ["v*"]', self.ci)
        self.assertIn("cancel-in-progress: true", self.ci)
        self.assertRegex(self.ci, r"timeout-minutes: \d+")

    def test_pages_waits_for_complete_main_validation_without_rebuild(self) -> None:
        self.assertIn("workflow_run:", self.pages)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.pages)
        self.assertIn("github.event.workflow_run.head_sha", self.pages)
        self.assertIn("github.ref == 'refs/heads/main'", self.pages)
        self.assertNotIn("run: .venv/bin/python scripts/build_publication.py", self.pages)
        self.assertLess(
            self.pages.index("actions/deploy-pages@"),
            self.pages.index("scripts/verify_deployment.py"),
        )

    def test_third_party_actions_use_immutable_commits(self) -> None:
        actions = re.findall(r"uses:\s+[^@\s]+@([^\s]+)", self.ci + self.pages)
        self.assertTrue(actions)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", value) for value in actions))


if __name__ == "__main__":
    unittest.main()
