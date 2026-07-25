from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_okf_bundle  # noqa: E402
import okf_semantic  # noqa: E402
import update_viewer  # noqa: E402


class OkfSemanticTest(unittest.TestCase):
    fixture_root = ROOT / "tests" / "fixtures" / "yaml_ld"

    def test_yaml_ld_frontmatter_parses_and_expands_with_pinned_context(self) -> None:
        page = okf_semantic.parse_markdown(self.fixture_root / "concept.md")
        self.assertEqual("https://example.gov.uk/okf/concepts/example", page.metadata["@id"])
        self.assertEqual(["example", "government"], page.metadata["tags"])
        self.assertEqual("human:fixture-reviewer", page.metadata["verified"]["by"])
        self.assertEqual("https://www.gov.uk/example", page.metadata["sources"][0]["resource"])
        self.assertIn("Human-readable Markdown", page.body)
        self.assertFalse(okf_semantic.schema_errors(page.metadata, "concept.schema.json"))
        expanded = okf_semantic.expand(page.metadata)
        self.assertEqual("https://example.gov.uk/okf/concepts/example", expanded[0]["@id"])
        self.assertIn("http://purl.org/dc/terms/title", expanded[0])

    def test_bundle_descriptor_matches_profile_schema(self) -> None:
        bundle = okf_semantic.load_yaml_ld(self.fixture_root / "bundle.yamlld")
        self.assertIsInstance(bundle, dict)
        assert isinstance(bundle, dict)
        self.assertEqual([], okf_semantic.schema_errors(bundle, "bundle.schema.json"))
        self.assertTrue(okf_semantic.expand(bundle))

    def test_yaml_12_and_yaml_ld_representation_rules(self) -> None:
        document = okf_semantic.load_yaml_ld_text("yes: no\nwhen: 2026-07-11\n")
        self.assertEqual({"yes": "no", "when": "2026-07-11"}, document)
        with self.assertRaises(okf_semantic.SemanticError):
            okf_semantic.load_yaml_ld_text("value: .inf\n")
        with self.assertRaises(okf_semantic.SemanticError):
            okf_semantic.load_yaml_ld_text("? [not, a, string]\n: invalid\n")

    def test_remote_contexts_are_allowlisted(self) -> None:
        with self.assertRaises(okf_semantic.SemanticError):
            okf_semantic.expand({"@context": "https://untrusted.example/context", "@id": "https://example.test/item"})

    def test_canonical_corpus_and_projection_are_okf_v02(self) -> None:
        graph, errors = update_viewer.build_graph()
        self.assertEqual([], errors)
        self.assertEqual(155, len(graph["nodes"]))
        self.assertEqual(579, len(graph["edges"]))
        root = graph["nodes"]["index.md"]
        self.assertEqual("0.2", root["okf_version"])
        self.assertEqual("Index", root["type"])
        source = graph["nodes"]["standards/openapi.md"]
        self.assertNotIn("timestamp", source)
        self.assertNotIn("verified", source)
        self.assertEqual("stable", source["status"])
        self.assertEqual(
            "https://spec.openapis.org/oas/v3.2.0.html",
            source["sources"][0]["resource"],
        )

        bundle, bundle_errors = build_okf_bundle.build_bundle()
        self.assertEqual([], bundle_errors)
        self.assertEqual("0.2", bundle["okf_version"])
        self.assertEqual(
            "process:okf-ai-infrastructure-publication",
            bundle["generated"]["by"],
        )
        projected = bundle["corpora"]["ai-infrastructure-wiki"]["nodes"][
            "standards/openapi.md"
        ]
        self.assertEqual(source["sources"], projected["sources"])

    def test_v02_optional_families_reject_invalid_dates_and_counts(self) -> None:
        errors = update_viewer.validate_v02_metadata(
            "bad.md",
            {
                "type": "Reference",
                "generated": {"by": "process:test", "at": "not-a-date"},
                "verified": {"by": "human:reviewer", "at": "still-not-a-date"},
                "stale_after": "2026-99-99",
                "sources": [
                    {
                        "resource": "scope descriptor",
                        "last_modified": "yesterday",
                        "usage_count": -1,
                    }
                ],
            },
        )
        self.assertIn("bad.md generated.at must be an ISO 8601 datetime", errors)
        self.assertIn("bad.md verified[0].at must be an ISO 8601 datetime", errors)
        self.assertIn("bad.md sources[0].last_modified must be an ISO date", errors)
        self.assertIn("bad.md sources[0].usage_count must be a non-negative integer", errors)
        self.assertIn("bad.md stale_after must be an ISO date", errors)


if __name__ == "__main__":
    unittest.main()
