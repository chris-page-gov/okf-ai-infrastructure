"""A visual must fail rather than invent paths or retain stale qualifications."""

import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_okf_bundle
import build_walkthrough
import semantic_projection


class WalkthroughTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle, errors = build_okf_bundle.build_bundle()
        assert not errors

    def test_visual_and_machine_trail_bind_graph_and_source_bytes(self):
        outputs = build_walkthrough.render_walkthrough(self.bundle)
        data = json.loads(outputs["walkthrough-data.json"])
        self.assertEqual(len(data["source_documents"]), 7)
        self.assertEqual(len(data["negative_controls"]), 2)
        graph = (json.dumps(semantic_projection.semantic_graph(self.bundle), ensure_ascii=False,
                            sort_keys=True, separators=(",", ":")) + "\n").encode()
        self.assertEqual(data["graph_sha256"], sha256(graph).hexdigest())
        for source in data["source_documents"]:
            self.assertEqual(source["sha256"], sha256((ROOT / source["route"]).read_bytes()).hexdigest())
        self.assertIn('<main>', outputs["walkthrough.html"])
        self.assertIn('role="img"', outputs["walkthrough.svg"])

    def test_a_nonexistent_relationship_cannot_be_drawn_as_an_edge(self):
        original = build_walkthrough.source_bytes
        case = json.loads(original("walkthrough.case.json", ROOT))
        case["trails"][0]["routes"] = ["federated/federated-rag.md", "uk-government/ncsc-secure-ai.md"]
        def changed(route, root):
            return json.dumps(case).encode() if route == "walkthrough.case.json" else original(route, root)
        with patch.object(build_walkthrough, "source_bytes", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "invent a directed relationship"):
                build_walkthrough.render_walkthrough(self.bundle)

    def test_new_verification_requires_the_authored_qualification_to_be_reviewed(self):
        changed = copy.deepcopy(self.bundle)
        changed["corpora"]["ai-infrastructure-wiki"]["nodes"]["federated/federated-rag.md"]["frontmatter"]["verified"] = {"by": "human:reviewer", "at": "2026-11-23"}
        with self.assertRaisesRegex(ValueError, "qualification no longer matches"):
            build_walkthrough.render_walkthrough(changed)


if __name__ == "__main__":
    unittest.main()
