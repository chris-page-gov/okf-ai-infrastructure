from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_publication_contract as checker  # noqa: E402


class PublicationContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = checker.load_contract()

    def test_repository_contract_is_locally_consistent(self) -> None:
        self.assertEqual([], checker.validate_contract(self.contract))

    def test_controlled_change_requires_guidance_and_changelog(self) -> None:
        self.assertEqual(
            [
                "controlled changes require CHANGELOG.md in the same change set",
                "controlled changes require README.md or AGENTS.md guidance in lockstep",
            ],
            checker.lockstep_errors(
                self.contract,
                ["scripts/build_publication.py"],
            ),
        )

    def test_controlled_change_accepts_lockstep_material(self) -> None:
        self.assertEqual(
            [],
            checker.lockstep_errors(
                self.contract,
                [
                    "scripts/build_publication.py",
                    "README.md",
                    "CHANGELOG.md",
                ],
            ),
        )


if __name__ == "__main__":
    unittest.main()
