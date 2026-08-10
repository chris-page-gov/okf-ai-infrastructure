from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import migrate_okf_v02  # noqa: E402
import okf_semantic  # noqa: E402
import semantic_projection  # noqa: E402
import update_viewer  # noqa: E402


class MarkdownFileSafetyTest(unittest.TestCase):
    def test_external_markdown_symlink_is_neither_ingested_nor_modified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = temporary / "repository"
            frameworks = repository / "frameworks"
            frameworks.mkdir(parents=True)
            (repository / "index.md").write_text("# Fixture root\n", encoding="utf-8")
            external = temporary / "external.md"
            external.write_text(
                "---\n"
                '"@id": https://example.test/external\n'
                '"@type": okf:Concept\n'
                "type: Concept\n"
                "title: External source\n"
                "description: This file must remain outside the repository.\n"
                "status: stable\n"
                "---\n"
                "# External source\n",
                encoding="utf-8",
            )
            original = external.read_bytes()
            linked_source = frameworks / "external.md"
            os.symlink(external, linked_source)

            with mock.patch.object(update_viewer, "ROOT", repository):
                graph, errors = update_viewer.build_graph()
            self.assertNotIn("frameworks/external.md", graph["nodes"])
            self.assertTrue(any("must not be a symlink" in error for error in errors), errors)

            nodes = {
                "frameworks/external.md": {
                    "@id": "https://example.test/external",
                    "@type": "okf:Concept",
                },
                "frameworks/target.md": {
                    "@id": "https://example.test/target",
                    "@type": "okf:Concept",
                },
            }
            with (
                mock.patch.object(semantic_projection, "ROOT", repository),
                self.assertRaisesRegex(okf_semantic.SemanticError, "must not be a symlink"),
            ):
                semantic_projection.rich_relationship(
                    "frameworks/external.md",
                    "frameworks/target.md",
                    nodes,
                    presentation_kind="related",
                    observed_at="2026-08-10T00:00:00Z",
                )

            with (
                mock.patch.object(migrate_okf_v02, "ROOT", repository),
                contextlib.redirect_stderr(io.StringIO()) as messages,
            ):
                self.assertEqual(1, migrate_okf_v02.main([]))
            self.assertIn("must not be a symlink", messages.getvalue())
            with self.assertRaisesRegex(
                okf_semantic.SemanticError, "destination must not be a symlink"
            ):
                okf_semantic.write_markdown_text(linked_source, "replacement\n")
            self.assertEqual(original, external.read_bytes())

    def test_migration_rejects_a_symlink_swap_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = temporary / "repository"
            frameworks = repository / "frameworks"
            frameworks.mkdir(parents=True)
            (repository / "index.md").write_text("# Fixture root\n", encoding="utf-8")
            concept = frameworks / "concept.md"
            concept.write_text(
                "---\n"
                "type: Concept\n"
                "title: Legacy concept\n"
                "description: Requires migration.\n"
                "timestamp: \"2026-08-10\"\n"
                "---\n"
                "# Legacy concept\n",
                encoding="utf-8",
            )
            external = temporary / "external.md"
            external.write_text("external target must not change\n", encoding="utf-8")
            original = external.read_bytes()
            real_writer = okf_semantic.write_markdown_text

            def swap_then_write(
                path: Path,
                text: str,
                *,
                repository_root: Path | None = None,
            ) -> None:
                self.assertEqual(concept, path)
                self.assertEqual(repository, repository_root)
                path.unlink()
                os.symlink(external, path)
                real_writer(path, text, repository_root=repository_root)

            with (
                mock.patch.object(migrate_okf_v02, "ROOT", repository),
                mock.patch.object(
                    migrate_okf_v02.okf_semantic,
                    "write_markdown_text",
                    side_effect=swap_then_write,
                ),
                contextlib.redirect_stderr(io.StringIO()) as messages,
            ):
                self.assertEqual(1, migrate_okf_v02.main([]))
            self.assertIn("destination must not be a symlink", messages.getvalue())
            self.assertEqual(original, external.read_bytes())

    def test_markdown_below_symlinked_directory_is_not_ingested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = temporary / "repository"
            repository.mkdir()
            external_directory = temporary / "external-frameworks"
            external_directory.mkdir()
            external = external_directory / "external.md"
            external.write_text(
                "---\n"
                '"@id": https://example.test/external\n'
                '"@type": okf:Concept\n'
                "type: Concept\n"
                "title: External source\n"
                "description: This file must remain outside the repository.\n"
                "status: stable\n"
                "---\n"
                "# External source\n",
                encoding="utf-8",
            )
            original = external.read_bytes()
            os.symlink(external_directory, repository / "frameworks")
            path_through_link = repository / "frameworks" / "external.md"

            with self.assertRaisesRegex(
                okf_semantic.SemanticError,
                "parent must not be a symlink",
            ):
                okf_semantic.read_markdown_text(
                    path_through_link,
                    repository_root=repository,
                )
            with self.assertRaisesRegex(
                okf_semantic.SemanticError,
                "parent must not be a symlink",
            ):
                okf_semantic.write_markdown_text(
                    path_through_link,
                    "replacement\n",
                    repository_root=repository,
                )
            self.assertEqual(original, external.read_bytes())


if __name__ == "__main__":
    unittest.main()
