from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import okf_semantic  # noqa: E402


class YamlLdBoundsTest(unittest.TestCase):
    def test_markdown_and_front_matter_byte_limits_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.md"
            path.write_bytes(b"x" * (okf_semantic.MARKDOWN_MAX_BYTES + 1))
            with self.assertRaisesRegex(
                okf_semantic.SemanticError, "Markdown source is .* limit"
            ):
                okf_semantic.parse_markdown(path)

        oversized_front_matter = "value: " + (
            "x" * okf_semantic.YAML_LD_MAX_BYTES
        )
        with self.assertRaisesRegex(
            okf_semantic.SemanticError, "YAML-LD input is .* limit"
        ):
            okf_semantic.load_yaml_ld_text(oversized_front_matter)

    def test_excessive_representation_depth_and_items_fail_closed(self) -> None:
        deep = "value:\n" + "".join(
            "  " * depth + "child:\n"
            for depth in range(1, okf_semantic.YAML_LD_MAX_DEPTH + 3)
        )
        deep += "  " * (okf_semantic.YAML_LD_MAX_DEPTH + 3) + "value: end\n"
        with self.assertRaisesRegex(
            okf_semantic.SemanticError, "nesting exceeds"
        ):
            okf_semantic.load_yaml_ld_text(deep)

        too_many = "values:\n" + "  - item\n" * okf_semantic.YAML_LD_MAX_ITEMS
        with self.assertRaisesRegex(
            okf_semantic.SemanticError, "representation exceeds .* items"
        ):
            okf_semantic.load_yaml_ld_text(too_many)

    def test_yaml_alias_fan_out_is_rejected_before_construction(self) -> None:
        alias_fan_out = (
            "base: &base [one, two, three, four]\n"
            "level_one: &level_one [*base, *base, *base, *base]\n"
            "level_two: [*level_one, *level_one, *level_one, *level_one]\n"
        )
        with self.assertRaisesRegex(
            okf_semantic.SemanticError, "anchors and aliases are not permitted"
        ):
            okf_semantic.load_yaml_ld_text(alias_fan_out)

    def test_yaml_stream_document_count_is_bounded(self) -> None:
        stream = "---\n" * okf_semantic.YAML_LD_MAX_DOCUMENTS + "---\nvalue: end\n"
        with self.assertRaisesRegex(
            okf_semantic.SemanticError,
            "stream exceeds .* documents",
        ):
            okf_semantic.load_yaml_ld_text(stream, allow_stream=True)


if __name__ == "__main__":
    unittest.main()
