from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_okf_bundle  # noqa: E402
import build_publication  # noqa: E402


class PublicationInventoryTest(unittest.TestCase):
    def source_root(self, directory: str) -> Path:
        root = Path(directory) / "source"
        (root / "corpus").mkdir(parents=True)
        for name in ("index.md", "sources-index.md", "log.md", "okf.config.json"):
            (root / name).write_text(f"{name}\n", encoding="utf-8")
        (root / "corpus" / "concept.md").write_text(
            "# Concept\n", encoding="utf-8"
        )
        return root

    def test_source_inventory_rejects_hidden_and_non_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.source_root(directory)
            hidden = root / "corpus" / ".DS_Store"
            hidden.write_bytes(b"metadata")
            with (
                mock.patch.object(build_publication, "DIRS", ("corpus",)),
                self.assertRaisesRegex(
                    ValueError, "unexpected publication source file: corpus/.DS_Store"
                ),
            ):
                build_publication.publication_source_files(root)

    def test_source_inventory_rejects_oversized_files_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.source_root(directory)
            with (
                mock.patch.object(build_publication, "DIRS", ("corpus",)),
                mock.patch.object(build_publication, "MAX_SOURCE_FILE_BYTES", 4),
                self.assertRaisesRegex(ValueError, "exceeds the 4-byte limit"),
            ):
                build_publication.publication_source_files(root)

    def test_source_and_output_inventory_reject_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.source_root(directory)
            external = Path(directory) / "external.md"
            external.write_text("# External\n", encoding="utf-8")
            (root / "corpus" / "linked.md").symlink_to(external)
            with (
                mock.patch.object(build_publication, "DIRS", ("corpus",)),
                self.assertRaisesRegex(
                    ValueError,
                    "publication source must not be a symlink: corpus/linked.md",
                ),
            ):
                build_publication.publication_source_files(root)

            output = Path(directory) / "output"
            output.mkdir()
            (output / "linked.json").symlink_to(external)
            files, errors = build_publication.publication_output_inventory(output)
            self.assertEqual(set(), files)
            self.assertIn(
                "published path must not be a symlink: linked.json",
                errors,
            )

    def test_release_counts_are_data_not_executable_constants(self) -> None:
        self.assertEqual(
            {"nodes": 3, "relationships": 2},
            build_okf_bundle.release_expected_counts(
                {"releaseExpectedCounts": {"nodes": 3, "relationships": 2}}
            ),
        )
        with self.assertRaisesRegex(ValueError, "contain exactly"):
            build_okf_bundle.release_expected_counts({})
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            build_okf_bundle.release_expected_counts(
                {"releaseExpectedCounts": {"nodes": True, "relationships": 2}}
            )


if __name__ == "__main__":
    unittest.main()
