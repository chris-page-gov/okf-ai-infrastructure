#!/usr/bin/env python3
"""Fail when producer-authored prose uses selected American spellings."""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]

# These trees contain generated copies, test/mutation literals, local tools or an
# immutable upstream profile. They are deliberately outside the authored-prose
# policy boundary.
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "bundle",
    "node_modules",
    "tests",
}
VENDORED_PROFILE = ("profiles", "bundle-wiki", "v1")

# This is an intentionally reviewed, deterministic vocabulary rather than a
# locale-dependent spell checker. Additions must include a focused test.
AMERICAN_TO_BRITISH = {
    "airplane": "aeroplane",
    "airplanes": "aeroplanes",
    "aluminum": "aluminium",
    "analyze": "analyse",
    "analyzed": "analysed",
    "analyzes": "analyses",
    "analyzing": "analysing",
    "artifact": "artefact",
    "artifacts": "artefacts",
    "authorization": "authorisation",
    "authorizations": "authorisations",
    "authorize": "authorise",
    "authorized": "authorised",
    "authorizes": "authorises",
    "authorizing": "authorising",
    "behavior": "behaviour",
    "behavioral": "behavioural",
    "behaviors": "behaviours",
    "canceled": "cancelled",
    "canceling": "cancelling",
    "catalog": "catalogue",
    "cataloged": "catalogued",
    "cataloging": "cataloguing",
    "catalogs": "catalogues",
    "center": "centre",
    "centered": "centred",
    "centering": "centring",
    "centers": "centres",
    "color": "colour",
    "colored": "coloured",
    "coloring": "colouring",
    "colors": "colours",
    "counselor": "counsellor",
    "counselors": "counsellors",
    "customization": "customisation",
    "customize": "customise",
    "customized": "customised",
    "customizes": "customises",
    "customizing": "customising",
    "defense": "defence",
    "dialog": "dialogue",
    "dialogs": "dialogues",
    "enrollment": "enrolment",
    "enrollments": "enrolments",
    "favor": "favour",
    "favored": "favoured",
    "favoring": "favouring",
    "favorite": "favourite",
    "favorites": "favourites",
    "favors": "favours",
    "fulfill": "fulfil",
    "fulfillment": "fulfilment",
    "fulfills": "fulfils",
    "gray": "grey",
    "honor": "honour",
    "honored": "honoured",
    "honoring": "honouring",
    "honors": "honours",
    "labeled": "labelled",
    "labeling": "labelling",
    "labor": "labour",
    "modeled": "modelled",
    "modeling": "modelling",
    "neighbor": "neighbour",
    "neighborhood": "neighbourhood",
    "neighborhoods": "neighbourhoods",
    "neighbors": "neighbours",
    "normalization": "normalisation",
    "normalize": "normalise",
    "normalized": "normalised",
    "normalizes": "normalises",
    "normalizing": "normalising",
    "optimization": "optimisation",
    "optimize": "optimise",
    "optimized": "optimised",
    "optimizes": "optimises",
    "optimizing": "optimising",
    "organization": "organisation",
    "organizational": "organisational",
    "organizations": "organisations",
    "organize": "organise",
    "organized": "organised",
    "organizes": "organises",
    "organizing": "organising",
    "prioritize": "prioritise",
    "prioritized": "prioritised",
    "prioritizes": "prioritises",
    "prioritizing": "prioritising",
    "recognize": "recognise",
    "recognized": "recognised",
    "recognizes": "recognises",
    "recognizing": "recognising",
    "sidewalk": "pavement",
    "sidewalks": "pavements",
    "standardization": "standardisation",
    "standardize": "standardise",
    "standardized": "standardised",
    "standardizes": "standardises",
    "standardizing": "standardising",
    "summarize": "summarise",
    "summarized": "summarised",
    "summarizes": "summarises",
    "summarizing": "summarising",
    "traveled": "travelled",
    "traveler": "traveller",
    "travelers": "travellers",
    "traveling": "travelling",
    "utilization": "use",
    "utilize": "use",
    "utilized": "used",
    "utilizes": "uses",
    "utilizing": "using",
    "visualization": "visualisation",
    "visualizations": "visualisations",
    "visualize": "visualise",
    "visualized": "visualised",
    "visualizes": "visualises",
    "visualizing": "visualising",
}

# Exact names which must not be localised. Keep this list narrow and auditable.
OFFICIAL_TITLES = (
    "Centers for Disease Control and Prevention",
    "Defense Innovation Unit",
    "Department of Defense",
    "U.S. Department of Defense",
    "US Department of Defense",
)

# Exact values governed by OKF or its profile. These are exempt only when they
# are syntactically represented as code/a quoted token, or occupy a technical
# front-matter field; ordinary prose using the same spelling is still checked.
GOVERNED_IDENTIFIERS = frozenset(
    {
        "historical",
        "inferred",
        "license",
        "model-derived",
        "normalization",
        "normalized",
        "official",
        "synthetic",
    }
)
GOVERNED_FRONT_MATTER_FIELDS = frozenset(
    {
        "@context",
        "@id",
        "@type",
        "assertion_scope",
        "assertion_status",
        "derivation",
        "id",
        "kind",
        "okf_version",
        "predicate",
        "source",
        "source_iri",
        "status",
        "target",
        "target_iri",
        "type",
    }
)

WORD_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(
        sorted((re.escape(word) for word in AMERICAN_TO_BRITISH), key=len, reverse=True)
    ) + r")(?![A-Za-z])",
    re.IGNORECASE,
)
URL_RE = re.compile(r"(?i)\b(?:https?://|mailto:)[^\s<>{}\[\]\"']+")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
MACHINE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_@./:+-]+$")
IDENTIFIER_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:--?[A-Za-z0-9][A-Za-z0-9_-]*|"
    r"[A-Za-z_][A-Za-z0-9_]*(?:[._:/-][A-Za-z0-9_@.-]+)+)(?![A-Za-z0-9_])"
)
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>\n]*>")
CSS_DECLARATION_RE = re.compile(r"(?<!\w)[A-Za-z-]+\s*:[^;}\n]+[;}]?")


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    column: int
    found: str
    preferred: str

    def render(self) -> str:
        return (
            f"{self.path}:{self.line}:{self.column}: American spelling "
            f"{self.found!r}; use {self.preferred!r} in producer-authored prose"
        )


@dataclass(frozen=True)
class ScanResult:
    findings: tuple[Finding, ...]
    markdown_files: int
    python_files: int


def _mask(chars: list[str], start: int, end: int) -> None:
    for index in range(max(start, 0), min(end, len(chars))):
        if chars[index] not in "\r\n":
            chars[index] = " "


def _mask_matches(chars: list[str], text: str, pattern: re.Pattern[str]) -> None:
    for match in pattern.finditer(text):
        _mask(chars, match.start(), match.end())


def _mask_literal(chars: list[str], text: str, literal: str) -> None:
    start = 0
    while True:
        index = text.find(literal, start)
        if index < 0:
            return
        _mask(chars, index, index + len(literal))
        start = index + len(literal)


def _mask_common(text: str) -> str:
    chars = list(text)
    _mask_matches(chars, text, URL_RE)
    _mask_matches(chars, text, INLINE_CODE_RE)
    _mask_matches(chars, text, IDENTIFIER_RE)
    _mask_matches(chars, text, HTML_TAG_RE)
    _mask_matches(chars, text, CSS_DECLARATION_RE)
    for title in OFFICIAL_TITLES:
        _mask_literal(chars, text, title)
    for identifier in GOVERNED_IDENTIFIERS:
        quoted = re.compile(
            rf"(?P<quote>['\"`]){re.escape(identifier)}(?P=quote)", re.IGNORECASE
        )
        _mask_matches(chars, text, quoted)
    return "".join(chars)


def _mask_markdown(text: str) -> str:
    chars = list(_mask_common(text))
    lines = text.splitlines(keepends=True)
    offset = 0
    fence: str | None = None
    in_front_matter = bool(lines and lines[0].strip() == "---")
    governed_list_indent: int | None = None

    for line_number, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        fence_match = re.match(r"(?:`{3,}|~{3,})", stripped)
        if fence is not None:
            _mask(chars, offset, offset + len(line))
            if fence_match and stripped.startswith(fence):
                fence = None
            offset += len(line)
            continue
        if fence_match:
            fence = fence_match.group(0)
            _mask(chars, offset, offset + len(line))
            offset += len(line)
            continue

        if line_number == 1 and in_front_matter:
            _mask(chars, offset, offset + len(line))
            offset += len(line)
            continue
        if in_front_matter and line.strip() in {"---", "..."}:
            in_front_matter = False
            governed_list_indent = None
            _mask(chars, offset, offset + len(line))
            offset += len(line)
            continue

        if in_front_matter:
            key_match = re.match(r"\s*([@A-Za-z_][@A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
            if key_match:
                key = key_match.group(1)
                value = key_match.group(2).rstrip("\r\n")
                governed_list_indent = (
                    indent if key in GOVERNED_FRONT_MATTER_FIELDS else None
                )
                if key in GOVERNED_FRONT_MATTER_FIELDS or _machine_value(value):
                    value_start = offset + key_match.start(2)
                    _mask(chars, value_start, value_start + len(value))
            elif governed_list_indent is not None:
                list_match = re.match(r"\s*-\s*(.*)$", line)
                if indent > governed_list_indent and list_match:
                    _mask(
                        chars,
                        offset + list_match.start(1),
                        offset + list_match.end(1),
                    )
                elif line.strip() and indent <= governed_list_indent:
                    governed_list_indent = None

        # Markdown destinations and reference definitions are technical; their
        # visible labels remain subject to the prose check unless allowlisted.
        for match in re.finditer(r"\]\(([^)\n]*)\)", line):
            _mask(
                chars,
                offset + match.start(1),
                offset + match.end(1),
            )
        reference = re.match(r"\s*\[[^\]]+\]:\s*(\S+)", line)
        if reference:
            _mask(chars, offset + reference.start(1), offset + reference.end(1))
        if re.match(r"\s*>", line):
            _mask(chars, offset, offset + len(line))

        offset += len(line)

    return "".join(chars)


def _machine_value(value: str) -> bool:
    stripped = value.strip().strip("'\"")
    return bool(stripped and MACHINE_TOKEN_RE.fullmatch(stripped))


def _line_column(text: str, index: int, base_line: int, base_column: int) -> tuple[int, int]:
    before = text[:index]
    line_offset = before.count("\n")
    if line_offset:
        column = len(before.rsplit("\n", 1)[-1]) + 1
    else:
        column = base_column + index + 1
    return base_line + line_offset, column


def _find_in_text(
    text: str,
    relative_path: str,
    *,
    base_line: int = 1,
    base_column: int = 0,
    markdown: bool = False,
) -> list[Finding]:
    masked = _mask_markdown(text) if markdown else _mask_common(text)
    findings: list[Finding] = []
    for match in WORD_RE.finditer(masked):
        found = text[match.start() : match.end()]
        preferred = AMERICAN_TO_BRITISH[found.lower()]
        line, column = _line_column(text, match.start(), base_line, base_column)
        findings.append(Finding(relative_path, line, column, found, preferred))
    return findings


def check_markdown(text: str, relative_path: str = "document.md") -> list[Finding]:
    """Return British-English findings for one authored Markdown document."""

    return _find_in_text(text, relative_path, markdown=True)


def _string_value(token_text: str) -> str | None:
    try:
        value = ast.literal_eval(token_text)
    except (SyntaxError, ValueError):
        # F-strings cannot be safely reduced to one value. Scanning their raw
        # source still checks human text and masks identifiers/expressions.
        return token_text
    return value if isinstance(value, str) else None


def check_python(text: str, relative_path: str = "script.py") -> list[Finding]:
    """Check human-facing Python comments and string literals."""

    findings: list[Finding] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comment = token.string[1:]
                findings.extend(
                    _find_in_text(
                        comment,
                        relative_path,
                        base_line=token.start[0],
                        base_column=token.start[1] + 1,
                    )
                )
            elif token.type == tokenize.STRING:
                value = _string_value(token.string)
                if value is None or _machine_value(value):
                    continue
                # Scan raw source so reported columns point to the repository
                # file, including prefixes and quote delimiters.
                findings.extend(
                    _find_in_text(
                        token.string,
                        relative_path,
                        base_line=token.start[0],
                        base_column=token.start[1],
                    )
                )
    except (IndentationError, tokenize.TokenError) as exc:
        raise ValueError(f"cannot tokenize {relative_path}: {exc}") from exc
    return findings


def _excluded(relative_path: Path) -> bool:
    parts = relative_path.parts
    if any(part in EXCLUDED_PARTS for part in parts):
        return True
    return parts[: len(VENDORED_PROFILE)] == VENDORED_PROFILE


def authored_files(root: Path) -> Iterable[Path]:
    """Yield policy-scoped Markdown and Python files in stable path order."""

    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.suffix.lower() not in {".md", ".py"}:
            continue
        relative = path.relative_to(root)
        if not _excluded(relative):
            yield path


def scan_repository(root: Path = ROOT) -> ScanResult:
    findings: list[Finding] = []
    markdown_files = 0
    python_files = 0
    for path in authored_files(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".md":
            markdown_files += 1
            findings.extend(check_markdown(text, relative))
        else:
            python_files += 1
            findings.extend(check_python(text, relative))
    return ScanResult(tuple(sorted(findings)), markdown_files, python_files)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    if len(arguments) > 1:
        print("usage: check_british_english.py [repository-root]", file=sys.stderr)
        return 2
    root = Path(arguments[0]).resolve() if arguments else ROOT
    result = scan_repository(root)
    if result.findings:
        for finding in result.findings:
            print(finding.render(), file=sys.stderr)
        print(
            f"British-English check failed with {len(result.findings)} finding(s).",
            file=sys.stderr,
        )
        return 1
    print(
        "British-English check passed: "
        f"{result.markdown_files} Markdown and {result.python_files} Python files checked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
