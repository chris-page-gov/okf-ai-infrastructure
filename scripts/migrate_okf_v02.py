#!/usr/bin/env python3
"""Mechanically migrate this bundle's legacy OKF v0.1 frontmatter to v0.2.

The legacy ``timestamp`` values on source-backed concepts describe the
referenced material, not a known content-generation event, so they become
``sources[].last_modified``.  The actor-free ``verified: "yes"`` flag cannot
be promoted to v0.2 verification without inventing an actor and event time.
Reserved index/log metadata is synthesized only in the Explorer projection.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OKF_ROOT_FILES = {"index.md", "sources-index.md", "log.md"}
OKF_DIRS = {
    "document",
    "federated",
    "frameworks",
    "glossary",
    "organisations",
    "research",
    "stack",
    "standards",
    "uk-government",
}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def iter_markdown() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*.md"):
        parts = path.relative_to(ROOT).parts
        if not parts or parts[0] in {"_site", "bundle", "tmp"}:
            continue
        if parts[0] in OKF_DIRS or (len(parts) == 1 and parts[0] in OKF_ROOT_FILES):
            paths.append(path)
    return sorted(paths)


def split_frontmatter(path: Path, text: str) -> tuple[list[str], str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path.relative_to(ROOT)} has unterminated frontmatter")
    return text[4:end].splitlines(), text[end + 5 :]


def scalar_line(lines: list[str], key: str) -> str | None:
    prefix = f"{key}:"
    values = [line[len(prefix) :].strip() for line in lines if line.startswith(prefix)]
    if len(values) > 1:
        raise ValueError(f"duplicate {key}")
    return values[0] if values else None


def migrate_text(path: Path, text: str) -> str:
    split = split_frontmatter(path, text)
    if split is None:
        return text
    lines, body = split
    relative = path.relative_to(ROOT)

    if relative == Path("index.md"):
        return '---\nokf_version: "0.2"\n---\n' + body
    if path.name in {"index.md", "log.md"}:
        return body

    timestamp = scalar_line(lines, "timestamp")
    verified = scalar_line(lines, "verified")
    resource = scalar_line(lines, "resource")
    if timestamp is None:
        return text
    if verified not in {None, '"yes"', "'yes'", "yes"}:
        raise ValueError(f"{relative} has a nonstandard legacy verified value")

    migrated = [
        line
        for line in lines
        if not line.startswith("timestamp:") and not line.startswith("verified:")
    ]
    if not any(line.startswith("status:") for line in migrated):
        migrated.append("status: stable")
    if resource and not any(line.startswith("sources:") for line in migrated):
        date_match = DATE_RE.search(timestamp)
        migrated.extend(
            [
                "sources:",
                f"  - resource: {resource}",
                *(
                    [f'    last_modified: "{date_match.group(0)}"']
                    if date_match
                    else []
                ),
            ]
        )
    return "---\n" + "\n".join(migrated) + "\n---\n" + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    pending: list[tuple[Path, str]] = []
    for path in iter_markdown():
        current = path.read_text(encoding="utf-8")
        migrated = migrate_text(path, current)
        if migrated != current:
            pending.append((path, migrated))
    if args.check:
        if pending:
            for path, _content in pending:
                print(f"needs OKF v0.2 migration: {path.relative_to(ROOT)}")
            return 1
        print("canonical Markdown is migrated to OKF v0.2")
        return 0
    for path, content in pending:
        path.write_text(content, encoding="utf-8")
    print(f"migrated {len(pending)} Markdown files to OKF v0.2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
