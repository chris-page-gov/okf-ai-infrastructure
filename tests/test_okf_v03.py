"""Core 0.3 adoption, safe metadata preservation and independent graph checks."""

import copy
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_okf_bundle
import okf_semantic
import semantic_projection
import update_viewer


class Core03Tests(unittest.TestCase):
    def test_contract_version_cannot_relabel_the_frozen_v1_schema(self):
        contract = json.loads((ROOT / "okf.semantic.json").read_text())
        v2 = json.loads((ROOT / "profiles/bundle-wiki/v2/repository-contract.schema.json").read_text())
        v1 = json.loads((ROOT / "profiles/bundle-wiki/v1/repository-contract.schema.json").read_text())
        self.assertEqual(list(Draft202012Validator(v2).iter_errors(contract)), [])
        self.assertTrue(list(Draft202012Validator(v1).iter_errors(contract)))

    def test_commonmark_code_is_not_a_link_and_reference_links_are_edges(self):
        body = "```md\n[Example](fiction.md)\n```\n[Evidence][source]\n\n[source]: /b.md#detail\n"
        self.assertEqual(update_viewer.find_edges("a.md", body, {"a.md", "b.md"}),
                         ([("a.md", "b.md")], []))

    def test_rfc3339_dates_and_single_source_are_supported_without_naive_times(self):
        metadata = {"type": "Reference", "generated": {"by": "process:test", "at": "2026-11-23"},
                    "sources": {"resource": "https://example.org/", "last_modified": "2026-11-23T14:00:00Z"}}
        self.assertEqual(update_viewer.validate_v02_metadata("a.md", metadata), [])
        metadata["generated"]["at"] = "2026-11-23T14:00:00"
        self.assertTrue(update_viewer.validate_v02_metadata("a.md", metadata))
        metadata["sources"] = [42]
        self.assertTrue(update_viewer.validate_v02_metadata("a.md", metadata))

    def test_complete_frontmatter_is_an_inert_json_literal_in_rdf_expansion(self):
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual(errors, [])
        route = "federated/federated-rag.md"
        node = bundle["corpora"]["ai-infrastructure-wiki"]["nodes"][route]
        node["frontmatter"]["x-future"] = {"@context": "https://untrusted.example/context", "value": "on"}
        semantic = semantic_projection.semantic_graph(bundle)
        expanded = okf_semantic.expand(semantic)
        graph = expanded[0]["@graph"]
        row = next(item for item in graph if item.get("@id") == node["semantic_id"])
        literal = row["https://chris-page-gov.github.io/okf-explorer/ns#authoredFrontmatter"][0]
        self.assertEqual(literal["@type"], "@json")
        self.assertEqual(literal["@value"], node["frontmatter"])

    def test_navigation_cannot_be_misrepresented_as_a_core_concept(self):
        bundle, errors = build_okf_bundle.build_bundle()
        self.assertEqual(errors, [])
        semantic = semantic_projection.semantic_graph(bundle)
        iri = bundle["corpora"]["ai-infrastructure-wiki"]["nodes"]["index.md"]["semantic_id"]
        row = next(item for item in semantic["@graph"] if item.get("@id") == iri)
        row["core_role"] = "concept"
        self.assertTrue(any("core role" in error for error in semantic_projection.validate_relationships(bundle, semantic)))


if __name__ == "__main__":
    unittest.main()
