"""Compare every published core concept with the independent Explorer import."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(projection: Path) -> dict:
    if projection.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("independent source projection exceeds its budget")
    imported = json.loads(projection.read_bytes())
    bundle = json.loads((ROOT / "bundle/okf-bundle.json").read_bytes())
    corpus = bundle["corpora"]["ai-infrastructure-wiki"]
    concepts = {route: node for route, node in corpus["nodes"].items()
                if node["core_role"] == "concept"}
    if set(concepts) != set(imported["nodes"]):
        raise ValueError("published core concept coverage differs from source")
    for route, node in concepts.items():
        source = imported["nodes"][route]
        if node["frontmatter"] != source["frontmatter"] or node["body"] != source["body"]:
            raise ValueError(f"published frontmatter or body differs from source: {route}")
    actual = {(row["source"], row["target"]) for row in corpus["relationships"]
              if row["relationship_role"] == "concept"}
    expected = {(row["source"], row["target"]) for row in imported["edges"]}
    if actual != expected:
        raise ValueError("published core reference graph differs from the independent source graph")
    return {"schema": "okf-core-projection-parity.v1", "status": "passed",
            "concepts": len(concepts), "directed_core_reference_pairs": len(expected),
            "source_projection_sha256": sha256(projection.read_bytes()).hexdigest(),
            "descriptor_sha256": sha256((ROOT / "bundle/okf-bundle.json").read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("projection", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT / "bundle"):
        parser.error("Write the receipt outside the published bundle")
    result = check(args.projection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(f"Independent core parity passed: {result['concepts']} concepts and {result['directed_core_reference_pairs']} reference pairs")
