from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_okf_bundle  # noqa: E402
import semantic_projection  # noqa: E402
import update_viewer  # noqa: E402


class SemanticContextInjectionTest(unittest.TestCase):
    fixture_root = ROOT / "tests" / "fixtures" / "semantic_domain"

    def test_authored_front_matter_rejects_json_ld_control_fields(self) -> None:
        marker = "    \"@type\": [rdf:Statement, okf:RelationshipAssertion]\n"
        cases = {
            "@context": (
                "    \"@context\":\n"
                "      source:\n"
                "        \"@id\": https://evil.example/not-subject\n"
                "        \"@type\": \"@id\"\n"
            ),
            "@reverse": (
                "    \"@reverse\":\n"
                "      https://evil.example/hidden:\n"
                "        \"@id\": https://evil.example/object\n"
            ),
        }
        for field, injected_yaml in cases.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                fixture = Path(directory) / "fixture"
                shutil.copytree(self.fixture_root, fixture)
                source_path = fixture / "frameworks" / "source.md"
                source = source_path.read_text(encoding="utf-8")
                self.assertIn(marker, source)
                source_path.write_text(
                    source.replace(marker, marker + injected_yaml, 1),
                    encoding="utf-8",
                )

                with (
                    mock.patch.object(update_viewer, "ROOT", fixture),
                    mock.patch.object(semantic_projection, "ROOT", fixture),
                    mock.patch.object(
                        build_okf_bundle,
                        "CONFIG",
                        fixture / "okf.config.json",
                    ),
                    self.assertRaisesRegex(
                        ValueError,
                        rf"assertion must not declare assertion-local JSON-LD .*{field}",
                    ),
                ):
                    build_okf_bundle.build_bundle()

    def test_runtime_json_ld_control_fields_cannot_receive_a_passing_receipt(
        self,
    ) -> None:
        original, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        clean_semantic = semantic_projection.semantic_graph(original)
        cases = {
            "@context": {
                "source": {
                    "@id": "https://evil.example/not-subject",
                    "@type": "@id",
                }
            },
            "@graph": [],
            "@reverse": {},
            "@id": "https://evil.example/replacement-assertion",
            "@type": "https://evil.example/ReplacementType",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                bundle = copy.deepcopy(original)
                relationship = bundle["corpora"]["ai-infrastructure-wiki"][
                    "relationships"
                ][0]
                relationship[field] = value

                validation_errors = semantic_projection.validate_relationships(
                    bundle, clean_semantic
                )
                self.assertTrue(
                    any(
                        "forbidden assertion-local JSON-LD control" in error
                        and field in error
                        for error in validation_errors
                    ),
                    validation_errors,
                )
                with self.assertRaisesRegex(
                    ValueError, "cannot issue a passing semantic receipt"
                ):
                    semantic_projection.semantic_validation_receipt(
                        bundle, clean_semantic
                    )
                with self.assertRaisesRegex(
                    ValueError, "must not contain assertion-local JSON-LD"
                ):
                    semantic_projection.semantic_assertion(relationship)
                with self.assertRaisesRegex(
                    ValueError, "must not contain assertion-local JSON-LD"
                ):
                    semantic_projection.semantic_graph(bundle)

    def test_nested_evidence_context_cannot_receive_a_passing_receipt(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        clean_semantic = semantic_projection.semantic_graph(bundle)
        relationship = bundle["corpora"]["ai-infrastructure-wiki"][
            "relationships"
        ][0]
        relationship["evidence"][0]["@context"] = {
            "url": {
                "@id": "https://evil.example/not-evidence-url",
                "@type": "@id",
            }
        }

        validation_errors = semantic_projection.validate_relationships(
            bundle, clean_semantic
        )
        self.assertTrue(
            any(
                "evidence[0].@context" in error for error in validation_errors
            ),
            validation_errors,
        )
        with self.assertRaisesRegex(
            ValueError, "cannot issue a passing semantic receipt"
        ):
            semantic_projection.semantic_validation_receipt(bundle, clean_semantic)
        with self.assertRaisesRegex(
            ValueError, r"evidence\[0\]\.@context"
        ):
            semantic_projection.semantic_graph(bundle)


if __name__ == "__main__":
    unittest.main()
