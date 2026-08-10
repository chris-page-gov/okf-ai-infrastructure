from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_british_english  # noqa: E402


class BritishEnglishTest(unittest.TestCase):
    def test_american_prose_is_rejected_with_actionable_locations(self) -> None:
        findings = check_british_english.check_markdown(
            "# Review\n\nThe organization centers color behavior.\n",
            "notes/review.md",
        )
        self.assertEqual(
            [
                ("notes/review.md", 3, 5, "organization", "organisation"),
                ("notes/review.md", 3, 18, "centers", "centres"),
                ("notes/review.md", 3, 26, "color", "colour"),
                ("notes/review.md", 3, 32, "behavior", "behaviour"),
            ],
            [
                (
                    finding.path,
                    finding.line,
                    finding.column,
                    finding.found,
                    finding.preferred,
                )
                for finding in findings
            ],
        )
        self.assertIn("notes/review.md:3:5", findings[0].render())

    def test_british_prose_is_accepted(self) -> None:
        findings = check_british_english.check_markdown(
            "# Review\n\nThe organisation centres colour and behaviour.\n"
            "The catalogue records synchronised artefacts.\n"
        )
        self.assertEqual([], findings)

    def test_python_comments_and_human_strings_are_checked(self) -> None:
        findings = check_british_english.check_python(
            "# Describe the organization for readers.\n"
            "message = \"Use the authorized color.\"\n"
            "status = \"normalized\"\n",
            "scripts/example.py",
        )
        self.assertEqual(
            ["organization", "authorized", "color"],
            [finding.found for finding in findings],
        )
        self.assertEqual([1, 2, 2], [finding.line for finding in findings])

    def test_code_urls_governed_values_and_official_titles_are_preserved(self) -> None:
        text = """---
status: normalized
identifier: organization_center
---

Keep `normalized` and `organization_center` byte-exact.
See https://example.test/organization/color for the U.S. Department of Defense.
The Centers for Disease Control and Prevention is an official title.

```python
organization = {"color": "gray"}
```
"""
        self.assertEqual([], check_british_english.check_markdown(text))

    def test_generated_tests_and_vendored_profile_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "README.md": "The organisation uses colour.\n",
                "bundle/generated.md": "The organization uses color.\n",
                "tests/mutation.py": 'message = "The organization uses color."\n',
                "profiles/bundle-wiki/v1/index.md": "The artifact is normalized.\n",
                ".venv/example.py": '# The organization uses color.\n',
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            result = check_british_english.scan_repository(root)

        self.assertEqual((), result.findings)
        self.assertEqual(1, result.markdown_files)
        self.assertEqual(0, result.python_files)


if __name__ == "__main__":
    unittest.main()
