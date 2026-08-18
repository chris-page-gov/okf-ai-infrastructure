#!/usr/bin/env python3
"""Check the local OKF publication contract and documentation lockstep."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "okf.publication.json"
SEMANTIC_PROFILE = "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/"
REQUIRED_TOP_LEVEL = {
    "schema",
    "modified",
    "locale",
    "time_zone",
    "repository",
    "semantic_contract",
    "source_families",
    "boundaries",
    "planes",
    "tooling",
    "lockstep",
    "ci",
    "publication",
    "verification",
    "limitations",
}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHELL_CONTROL = re.compile(r"&&|\|\||[;`]|\$\(|[\r\n]")


def load_contract(path: Path = CONTRACT) -> dict[str, Any]:
    """Load strict JSON and reject duplicate keys."""

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs)
    if not isinstance(document, dict):
        raise ValueError("publication contract root must be an object")
    return document


def _ids(rows: object, label: str, errors: list[str]) -> set[str]:
    if not isinstance(rows, list):
        errors.append(f"{label} must be an array")
        return set()
    values: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            errors.append(f"{label}[{index}] has an invalid id")
        elif identifier in values:
            errors.append(f"{label} duplicates id {identifier}")
        else:
            values.add(identifier)
    return values


def _command_references(document: dict[str, Any]) -> list[tuple[str, object]]:
    references: list[tuple[str, object]] = []
    for family in document.get("source_families", []):
        if isinstance(family, dict):
            references.append(
                (
                    f"source family {family.get('id')}",
                    (family.get("extraction") or {}).get("command_ids", []),
                )
            )
    boundaries = document.get("boundaries") or {}
    for boundary in boundaries.get("generated", []):
        if isinstance(boundary, dict):
            references.extend(
                (
                    (f"generated boundary {boundary.get('path')} build", boundary.get("build_command_ids", [])),
                    (f"generated boundary {boundary.get('path')} check", boundary.get("check_command_ids", [])),
                )
            )
    for plane in document.get("planes", []):
        if isinstance(plane, dict):
            references.append((f"plane {plane.get('id')}", plane.get("command_ids", [])))
    lockstep = document.get("lockstep") or {}
    references.append(("lockstep", [lockstep.get("check_command_id")]))
    browser = (document.get("ci") or {}).get("browser") or {}
    for policy_name in ("ordinary", "cross_engine"):
        policy = browser.get(policy_name) or {}
        references.append((f"CI browser {policy_name}", policy.get("command_ids", [])))
        installation = policy.get("installation") or {}
        references.append(
            (f"CI browser {policy_name} installation", installation.get("command_ids", []))
        )
    references.append(
        ("verification", (document.get("verification") or {}).get("command_ids", []))
    )
    return references


def validate_contract(document: dict[str, Any]) -> list[str]:
    """Return local structural and cross-reference errors."""

    errors: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL - set(document))
    extra = sorted(set(document) - REQUIRED_TOP_LEVEL)
    if missing:
        errors.append("missing top-level fields: " + ", ".join(missing))
    if extra:
        errors.append("unknown top-level fields: " + ", ".join(extra))
    if document.get("schema") != "okf-repository-publication-contract.v1":
        errors.append("schema must be okf-repository-publication-contract.v1")
    if document.get("locale") != "en-GB":
        errors.append("locale must be en-GB")
    if document.get("time_zone") != "Europe/London":
        errors.append("time_zone must be Europe/London")

    repository = document.get("repository") or {}
    semantic = document.get("semantic_contract") or {}
    for label, value in (
        ("repository.root_index", repository.get("root_index")),
        ("semantic_contract.path", semantic.get("path")),
    ):
        if not isinstance(value, str) or not (ROOT / value).is_file():
            errors.append(f"{label} must name an existing file")
    if semantic.get("profile") != SEMANTIC_PROFILE:
        errors.append("semantic_contract.profile must name Bundle Wiki v1")

    source_ids = _ids(document.get("source_families"), "source_families", errors)
    plane_ids = _ids(document.get("planes"), "planes", errors)
    commands = (document.get("tooling") or {}).get("commands")
    command_ids = _ids(commands, "tooling.commands", errors)
    for command in commands if isinstance(commands, list) else []:
        if not isinstance(command, dict):
            continue
        value = command.get("command")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"command {command.get('id')} has no command string")
        elif SHELL_CONTROL.search(value):
            errors.append(f"command {command.get('id')} contains shell control syntax")
        source = command.get("source")
        if not isinstance(source, str) or not (ROOT / source).is_file():
            errors.append(f"command {command.get('id')} has no existing guidance source")
        if command.get("review_status") != "reviewed-local-guidance":
            errors.append(f"command {command.get('id')} is not reviewed local guidance")

    boundaries = document.get("boundaries") or {}
    for boundary in boundaries.get("authored", []):
        if isinstance(boundary, dict) and boundary.get("source_family_id") not in (
            None,
            *source_ids,
        ):
            errors.append(
                f"authored boundary {boundary.get('path')} references an unknown source family"
            )
    for plane in document.get("planes", []):
        if not isinstance(plane, dict):
            continue
        for dependency in plane.get("depends_on", []):
            if dependency not in plane_ids:
                errors.append(f"plane {plane.get('id')} depends on unknown plane {dependency}")
    for label, values in _command_references(document):
        if not isinstance(values, list):
            errors.append(f"{label} command_ids must be an array")
            continue
        for command_id in values:
            if command_id not in command_ids:
                errors.append(f"{label} references unknown command {command_id}")

    lockstep = document.get("lockstep") or {}
    if lockstep.get("changelog_path") != "CHANGELOG.md":
        errors.append("lockstep changelog_path must be CHANGELOG.md")
    if lockstep.get("dependency_update_policy") != (
        "assess-release-bound-bytes-no-blanket-exemption"
    ):
        errors.append("lockstep dependency update policy is not fail-closed")
    if lockstep.get("unknown_path_policy") != "fail-closed":
        errors.append("lockstep unknown path policy must fail closed")
    documentation_paths = set(lockstep.get("documentation_paths", []))
    for required in ("README.md", "AGENTS.md", "CHANGELOG.md"):
        if required not in documentation_paths:
            errors.append(f"lockstep documentation paths omit {required}")

    ci = document.get("ci") or {}
    for workflow in ci.get("workflow_paths", []):
        if not isinstance(workflow, str) or not (ROOT / workflow).is_file():
            errors.append(f"CI workflow path does not exist: {workflow}")
    publication = document.get("publication") or {}
    if publication.get("candidate_policy") != "promote-exact-assured-bytes-without-rebuild":
        errors.append("publication candidate policy must prohibit rebuilds")
    for target in publication.get("targets", []):
        if not isinstance(target, dict):
            continue
        if target.get("exact_commit_required") is not True:
            errors.append(f"publication target {target.get('id')} does not require an exact commit")
        if target.get("promote_without_rebuild") is not True:
            errors.append(f"publication target {target.get('id')} permits a rebuild")
    return sorted(set(errors))


def _matches(path: str, patterns: object) -> bool:
    return isinstance(patterns, list) and any(
        isinstance(pattern, str) and fnmatch.fnmatchcase(path, pattern)
        for pattern in patterns
    )


def lockstep_errors(document: dict[str, Any], changed_paths: list[str]) -> list[str]:
    """Require human guidance and the changelog with controlled changes."""

    lockstep = document["lockstep"]
    if not any(_matches(path, lockstep["controlled_paths"]) for path in changed_paths):
        return []
    changelog = lockstep["changelog_path"]
    documentation_patterns = [
        pattern
        for pattern in lockstep["documentation_paths"]
        if pattern != changelog
    ]
    errors: list[str] = []
    if changelog not in changed_paths:
        errors.append("controlled changes require CHANGELOG.md in the same change set")
    if not any(_matches(path, documentation_patterns) for path in changed_paths):
        errors.append("controlled changes require README.md or AGENTS.md guidance in lockstep")
    return errors


def event_base_sha() -> str | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    candidate = (event.get("pull_request") or {}).get("base", {}).get("sha")
    if not candidate:
        candidate = event.get("before")
    if isinstance(candidate, str) and FULL_SHA.fullmatch(candidate) and set(candidate) != {"0"}:
        return candidate
    return None


def git_changed_paths(base_sha: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(path for path in result.stdout.splitlines() if path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", help="Git commit used for lockstep comparison")
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Explicit changed path for a local lockstep probe",
    )
    args = parser.parse_args(argv)
    try:
        document = load_contract()
        errors = validate_contract(document)
        base_sha = args.base_ref or event_base_sha()
        changed_paths = args.changed_path or (
            git_changed_paths(base_sha) if base_sha else []
        )
        errors.extend(lockstep_errors(document, changed_paths))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"publication contract check failed: {exc}")
        return 1
    if errors:
        print("publication contract check failed:")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    suffix = f"; {len(changed_paths)} changed paths checked" if changed_paths else ""
    print(f"publication contract and documentation lockstep passed{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
