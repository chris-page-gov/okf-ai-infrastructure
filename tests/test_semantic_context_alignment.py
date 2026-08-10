from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_okf_bundle  # noqa: E402
import okf_semantic  # noqa: E402
import semantic_projection  # noqa: E402


OKF = "https://chris-page-gov.github.io/okf-explorer/ns#"
PROV = "http://www.w3.org/ns/prov#"
DCTERMS = "http://purl.org/dc/terms/"
XSD = "http://www.w3.org/2001/XMLSchema#"


def expanded_assertion(
    semantic: dict[str, Any], assertion_id: str
) -> dict[str, Any]:
    expanded = okf_semantic.expand(semantic)
    graph = expanded[0].get("@graph", []) if expanded else []
    return next(item for item in graph if item.get("@id") == assertion_id)


class SemanticContextAlignmentTest(unittest.TestCase):
    def test_inline_context_preserves_every_canonical_assertion_mapping(self) -> None:
        semantic_context = json.loads(
            okf_semantic.SEMANTIC_CONTEXT_PATH.read_text(encoding="utf-8")
        )
        canonical = semantic_context["@context"]["assertions"]["@context"]
        inline = semantic_projection.INLINE_ASSERTION_CONTEXT

        self.assertEqual(
            canonical,
            {key: inline[key] for key in canonical},
        )

    def test_current_assertion_values_expand_to_canonical_iris(self) -> None:
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        semantic = semantic_projection.semantic_graph(bundle)
        relationship = bundle["corpora"]["ai-infrastructure-wiki"][
            "relationships"
        ][0]
        assertion = expanded_assertion(semantic, relationship["id"])

        self.assertEqual(
            [{"@id": OKF + "NormalizedAssertion"}],
            assertion[OKF + "assertionStatus"],
        )
        self.assertEqual(
            [{"@id": OKF + "RealWorldScope"}],
            assertion[OKF + "assertionScope"],
        )
        authority = assertion[OKF + "authority"][0]
        self.assertEqual(
            [{"@id": OKF + "DerivedAuthority"}],
            authority[OKF + "authorityClass"],
        )
        self.assertIn(OKF + "rights", assertion)
        self.assertNotIn(DCTERMS + "rights", assertion)

    def test_inferred_and_model_fields_survive_expansion(self) -> None:
        original, errors = build_okf_bundle.build_bundle()
        self.assertEqual([], errors)
        cases = (
            ("inferred", "derived", "InferredAssertion", "DerivedAuthority"),
            (
                "model-derived",
                "model-assisted",
                "ModelDerivedAssertion",
                "ModelAssistedAuthority",
            ),
        )
        for status, authority_class, status_iri, authority_iri in cases:
            with self.subTest(status=status):
                bundle = copy.deepcopy(original)
                relationship = bundle["corpora"]["ai-infrastructure-wiki"][
                    "relationships"
                ][0]
                relationship["assertion_status"] = status
                relationship["authority"]["class"] = authority_class
                relationship["rule"] = (
                    semantic_projection.PUBLIC_BASE + "rules/rich-context-test"
                )
                relationship["supporting_assertions"] = [
                    semantic_projection.PUBLIC_BASE
                    + "assertions/rich-context-support"
                ]
                relationship["confidence_score"] = 0.875
                relationship["strength"] = 2.5
                relationship["count"] = 3
                relationship["stale_after"] = "2027-08-10T00:00:00Z"
                relationship["review_status"] = "reviewed"
                evidence = relationship["evidence"][0]
                evidence.update(
                    {
                        "resource": evidence["url"],
                        "field_provenance": "authored local Markdown link",
                        "source_value": "frameworks/context-hub.md",
                        "literal_sha256": "a" * 64,
                        "rule_id": relationship["rule"],
                        "rationale": "Exercises every canonical rich-field mapping.",
                    }
                )

                semantic = semantic_projection.semantic_graph(bundle)
                self.assertEqual(
                    [],
                    semantic_projection.validate_relationships(bundle, semantic),
                )
                assertion = expanded_assertion(semantic, relationship["id"])

                self.assertEqual(
                    [{"@id": OKF + status_iri}],
                    assertion[OKF + "assertionStatus"],
                )
                authority = assertion[OKF + "authority"][0]
                self.assertEqual(
                    [{"@id": OKF + authority_iri}],
                    authority[OKF + "authorityClass"],
                )
                self.assertEqual(
                    [{"@id": relationship["rule"]}],
                    assertion[OKF + "rule"],
                )
                self.assertEqual(
                    [{"@id": relationship["supporting_assertions"][0]}],
                    assertion[PROV + "wasDerivedFrom"],
                )
                for predicate in (
                    OKF + "confidenceScore",
                    OKF + "strength",
                    OKF + "count",
                    OKF + "staleAfter",
                    OKF + "reviewStatus",
                ):
                    self.assertIn(predicate, assertion)
                self.assertEqual(
                    XSD + "decimal",
                    assertion[OKF + "confidenceScore"][0]["@type"],
                )
                expanded_evidence = assertion[PROV + "hadPrimarySource"][0]
                for predicate in (
                    DCTERMS + "source",
                    OKF + "fieldProvenance",
                    OKF + "sourceValue",
                    OKF + "literalSha256",
                    OKF + "rule",
                    OKF + "rationale",
                ):
                    self.assertIn(predicate, expanded_evidence)


if __name__ == "__main__":
    unittest.main()
