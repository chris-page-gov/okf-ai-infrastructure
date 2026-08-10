#!/usr/bin/env python3
"""YAML-LD and Markdown front matter support for OKF bundle wikis."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker
from pyld import jsonld
from ruamel.yaml import YAML
from ruamel.yaml.tokens import AliasToken, AnchorToken

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = ROOT / "profiles" / "bundle-wiki" / "v1"
PROFILE_VENDOR_LOCK_PATH = ROOT / "profiles" / "bundle-wiki" / "v1.vendor-lock.json"
PROFILE_VENDOR_LOCK_SCHEMA = "okf-profile-vendor-lock.v1"
PROFILE_VENDOR_LOCK_SHA256 = (
    "979af714974abb093ac9d4b1b7e289597c61d33c24bb6959d9914c2f74dc6a09"
)
PROFILE_VENDOR_LOCK_BYTES = 3_281
PROFILE_VENDOR_FILE_COUNT = 16
PROFILE_VENDOR_MAX_FILE_BYTES = 16_384
PROFILE_JSON_MAX_DEPTH = 64
MARKDOWN_MAX_BYTES = 1_048_576
YAML_LD_MAX_BYTES = 131_072
YAML_LD_MAX_DEPTH = 64
YAML_LD_MAX_ITEMS = 10_000
YAML_LD_MAX_DOCUMENTS = 64
PROFILE_VENDOR_FILES = (
    "bundle.schema.json",
    "concept.schema.json",
    "context.jsonld",
    "governed-term-validation.schema.json",
    "governed-terms.schema.json",
    "index.md",
    "iri-route-registry.schema.json",
    "predicate-registry.schema.json",
    "presentation.schema.json",
    "provider-datapack-manifest.schema.json",
    "provider-datapack.schema.json",
    "repository-contract.schema.json",
    "semantic-assertion.schema.json",
    "semantic-context.jsonld",
    "semantic-model.schema.json",
    "shapes.ttl",
)
PROFILE_VENDOR_IDENTITY_ALGORITHM = "sha256"
PROFILE_VENDOR_IDENTITY_CANONICALISATION = (
    "profile-lock-lines-v1: UTF-8 lines in lexical path order: "
    "<path> TAB <bytes> TAB <sha256> LF"
)
PROFILE_VENDOR_RELEASE = {
    "repository": "https://github.com/chris-page-gov/okf-explorer",
    "version": "0.6.0",
    "tag": "v0.6.0",
    "tag_object": "d256a74419c2593c2bf2f3f5749c606fad5daf9d",
    "commit": "4bb7b92a64b7ba69bde9b1e86786217338cd166d",
    "git_tree": "d26ae9a818041ff74c469e653ec714632ddbfc2a",
}
SEMANTIC_ASSERTION_SCHEMA_PATH = PROFILE_ROOT / "semantic-assertion.schema.json"
SEMANTIC_ASSERTION_SCHEMA_ID = (
    "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/"
    "semantic-assertion.schema.json"
)
SEMANTIC_ASSERTION_SCHEMA_SHA256 = (
    "f69480328db4b64d678d9c50b6534d808000f7fb50a30e8cc9e3bf2facbcb8bc"
)
SEMANTIC_ASSERTION_SCHEMA_BYTES = 7_308
CONTEXT_PATH = PROFILE_ROOT / "context.jsonld"
SEMANTIC_CONTEXT_PATH = PROFILE_ROOT / "semantic-context.jsonld"
CONTEXT_URL = "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/context.jsonld"
SEMANTIC_CONTEXT_URL = "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/semantic-context.jsonld"
PROFILE_URL = "https://chris-page-gov.github.io/okf-explorer/profile/bundle-wiki/v1/"


class SemanticError(ValueError):
    """Raised when structured OKF metadata is not safe or conformant."""


@dataclass(frozen=True)
class MarkdownDocument:
    metadata: dict[str, Any]
    body: str


@dataclass(frozen=True)
class ProfileVendorVerification:
    errors: tuple[str, ...]
    files: dict[str, bytes] | None = None


@dataclass(frozen=True)
class SemanticAssertionSchemaVerification:
    errors: tuple[str, ...]
    raw: bytes | None = None
    schema: dict[str, Any] | None = None


def yaml_parser() -> YAML:
    """Return a safe YAML 1.2 parser that retains timestamps as strings."""
    parser = YAML(typ="safe", pure=True)
    parser.version = (1, 2)
    parser.allow_duplicate_keys = False
    parser.constructor.add_constructor(
        "tag:yaml.org,2002:timestamp",
        lambda constructor, node: constructor.construct_scalar(node),
    )
    return parser


def _validate_representation(
    value: Any,
    *,
    path: str = "$",
    active: set[int] | None = None,
    depth: int = 0,
    item_count: list[int] | None = None,
) -> None:
    if active is None:
        active = set()
    if item_count is None:
        item_count = [0]
    if depth > YAML_LD_MAX_DEPTH:
        raise SemanticError(
            f"{path}: YAML-LD nesting exceeds {YAML_LD_MAX_DEPTH} levels"
        )
    item_count[0] += 1
    if item_count[0] > YAML_LD_MAX_ITEMS:
        raise SemanticError(
            f"{path}: YAML-LD representation exceeds {YAML_LD_MAX_ITEMS} items"
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise SemanticError(f"{path}: non-finite numbers are not valid YAML-LD")
    if isinstance(value, dict):
        identity = id(value)
        if identity in active:
            raise SemanticError(f"{path}: YAML-LD representation graph contains a cycle")
        active.add(identity)
        for key, item in value.items():
            if not isinstance(key, str):
                raise SemanticError(f"{path}: YAML-LD mapping keys must be strings")
            _validate_representation(
                item,
                path=f"{path}.{key}",
                active=active,
                depth=depth + 1,
                item_count=item_count,
            )
        active.remove(identity)
    elif isinstance(value, list):
        identity = id(value)
        if identity in active:
            raise SemanticError(f"{path}: YAML-LD representation graph contains a cycle")
        active.add(identity)
        for index, item in enumerate(value):
            _validate_representation(
                item,
                path=f"{path}[{index}]",
                active=active,
                depth=depth + 1,
                item_count=item_count,
            )
        active.remove(identity)


def load_yaml_ld_text(text: str, *, source: str = "<string>", allow_stream: bool = False) -> dict[str, Any] | list[Any]:
    try:
        byte_count = len(text.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as exc:
        raise SemanticError(f"{source}: YAML-LD must be valid UTF-8 text") from exc
    if byte_count > YAML_LD_MAX_BYTES:
        raise SemanticError(
            f"{source}: YAML-LD input is {byte_count} bytes; "
            f"limit is {YAML_LD_MAX_BYTES}"
        )
    try:
        for token in yaml_parser().scan(text):
            if isinstance(token, (AnchorToken, AliasToken)):
                raise SemanticError(
                    f"{source}: YAML anchors and aliases are not permitted in YAML-LD"
                )
    except SemanticError:
        raise
    except Exception as exc:  # ruamel exposes several scanner-specific classes.
        raise SemanticError(f"{source}: invalid YAML-LD: {exc}") from exc

    documents: list[Any] = []
    document_count = 0
    try:
        for document in yaml_parser().load_all(text):
            document_count += 1
            if document_count > YAML_LD_MAX_DOCUMENTS:
                raise SemanticError(
                    f"{source}: YAML-LD stream exceeds "
                    f"{YAML_LD_MAX_DOCUMENTS} documents"
                )
            if document_count > 1 and not allow_stream:
                raise SemanticError(
                    f"{source}: OKF front matter and descriptors must contain "
                    "one YAML-LD document"
                )
            if document is not None:
                documents.append(document)
    except SemanticError:
        raise
    except Exception as exc:  # ruamel exposes several parser-specific error classes.
        raise SemanticError(f"{source}: invalid YAML-LD: {exc}") from exc
    if not documents:
        raise SemanticError(f"{source}: YAML-LD document is empty")
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise SemanticError(f"{source}: document {index + 1} must be a mapping")
        _validate_representation(document)
    return documents if allow_stream else documents[0]


def load_yaml_ld(path: Path, *, allow_stream: bool = False) -> dict[str, Any] | list[Any]:
    text = read_regular_utf8(
        path,
        max_bytes=YAML_LD_MAX_BYTES,
        label="YAML-LD document",
    )
    return load_yaml_ld_text(text, source=path.as_posix(), allow_stream=allow_stream)


def parse_markdown(
    path: Path,
    *,
    repository_root: Path | None = None,
) -> MarkdownDocument:
    text = read_markdown_text(path, repository_root=repository_root)
    if not text.startswith("---\n"):
        raise SemanticError(f"{path}: missing YAML front matter")
    end = text.find("\n---", 4)
    if end == -1:
        raise SemanticError(f"{path}: unterminated YAML front matter")
    raw = text[4:end]
    body = text[end + 4 :].lstrip("\n").strip("\n")
    metadata = load_yaml_ld_text(raw, source=f"{path.as_posix()} front matter")
    assert isinstance(metadata, dict)
    return MarkdownDocument(metadata=metadata, body=body)


def legacy_scalar(value: Any) -> str:
    """Project structured metadata into the legacy Explorer's string fields."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def legacy_frontmatter(metadata: dict[str, Any]) -> dict[str, str]:
    projected = {key: legacy_scalar(value) for key, value in metadata.items()}
    semantic_type = metadata.get("@type")
    if not projected.get("type") and semantic_type:
        if isinstance(semantic_type, list):
            semantic_type = semantic_type[0] if semantic_type else ""
        projected["type"] = str(semantic_type).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    if metadata.get("@id"):
        projected["semantic_id"] = str(metadata["@id"])
    if semantic_type:
        projected["semantic_type"] = legacy_scalar(semantic_type)
    return projected


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((PROFILE_ROOT / name).read_text(encoding="utf-8"))


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _profile_identity(rows: list[tuple[str, int, str]]) -> str:
    canonical = "".join(
        f"{path}\t{byte_count}\t{digest}\n"
        for path, byte_count, digest in sorted(rows)
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _exception_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {ascii(str(exc))}"


def _verify_repository_path_chain(
    path: Path,
    repository_root: Path,
    *,
    label: str,
) -> None:
    """Reject escapes and symlinked components below a trusted repository root."""
    absolute_path = Path(os.path.abspath(path))
    absolute_root = Path(os.path.abspath(repository_root))
    try:
        relative = absolute_path.relative_to(absolute_root)
    except ValueError as exc:
        raise SemanticError(
            f"{label} must remain inside repository root {absolute_root}: {path}"
        ) from exc

    current = absolute_root
    for component in relative.parts[:-1]:
        current /= component
        try:
            inspected = current.lstat()
        except (OSError, ValueError, RecursionError) as exc:
            raise SemanticError(
                f"{label} parent cannot be inspected: "
                f"{current}: {_exception_text(exc)}"
            ) from exc
        if stat.S_ISLNK(inspected.st_mode):
            raise SemanticError(
                f"{label} parent must not be a symlink: {current}"
            )
        if not stat.S_ISDIR(inspected.st_mode):
            raise SemanticError(
                f"{label} parent must be a directory: {current}"
            )


def read_regular_file_bytes(
    path: Path,
    *,
    max_bytes: int,
    label: str,
    repository_root: Path | None = None,
) -> bytes:
    """Read one bounded regular file without following repository symlinks."""
    if repository_root is not None:
        _verify_repository_path_chain(path, repository_root, label=label)
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise SemanticError(f"{label} is missing: {path}") from exc
    except (OSError, ValueError, RecursionError) as exc:
        raise SemanticError(
            f"{label} cannot be inspected: {path}: {_exception_text(exc)}"
        ) from exc
    if stat.S_ISLNK(before.st_mode):
        raise SemanticError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(before.st_mode):
        raise SemanticError(f"{label} must be a regular file: {path}")
    if before.st_size > max_bytes:
        raise SemanticError(
            f"{label} is {before.st_size} bytes; limit is {max_bytes}: {path}"
        )

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise SemanticError(f"{label} changed to a non-file while being read: {path}")
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise SemanticError(f"{label} changed while being read: {path}")
        if opened.st_size > max_bytes:
            raise SemanticError(
                f"{label} grew to {opened.st_size} bytes; limit is {max_bytes}: {path}"
            )
        remaining = max_bytes + 1
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    except SemanticError:
        raise
    except (OSError, ValueError, RecursionError) as exc:
        raise SemanticError(
            f"{label} cannot be read safely: {path}: {_exception_text(exc)}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw) > max_bytes:
        raise SemanticError(f"{label} exceeds {max_bytes} bytes: {path}")
    if (
        len(raw) != opened.st_size
        or after.st_size != opened.st_size
        or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
    ):
        raise SemanticError(f"{label} changed while being read: {path}")
    return raw


def read_regular_utf8(
    path: Path,
    *,
    max_bytes: int,
    label: str,
    repository_root: Path | None = None,
) -> str:
    raw = read_regular_file_bytes(
        path,
        max_bytes=max_bytes,
        label=label,
        repository_root=repository_root,
    )
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SemanticError(f"{label} must be UTF-8: {path}") from exc


def read_markdown_text(
    path: Path,
    *,
    repository_root: Path | None = None,
) -> str:
    return read_regular_utf8(
        path,
        max_bytes=MARKDOWN_MAX_BYTES,
        label="Markdown source",
        repository_root=repository_root,
    )


def write_markdown_text(
    path: Path,
    text: str,
    *,
    repository_root: Path | None = None,
) -> None:
    """Write a bounded Markdown file only through its verified regular inode."""
    try:
        raw = text.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise SemanticError(f"Markdown output must be UTF-8: {path}") from exc
    if len(raw) > MARKDOWN_MAX_BYTES:
        raise SemanticError(
            f"Markdown output is {len(raw)} bytes; limit is {MARKDOWN_MAX_BYTES}: {path}"
        )
    if repository_root is not None:
        _verify_repository_path_chain(
            path,
            repository_root,
            label="Markdown destination",
        )
    try:
        before = path.lstat()
    except (OSError, ValueError, RecursionError) as exc:
        raise SemanticError(
            f"Markdown destination cannot be inspected: {path}: {_exception_text(exc)}"
        ) from exc
    if stat.S_ISLNK(before.st_mode):
        raise SemanticError(f"Markdown destination must not be a symlink: {path}")
    if not stat.S_ISREG(before.st_mode):
        raise SemanticError(f"Markdown destination must be a regular file: {path}")

    flags = os.O_WRONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise SemanticError(
                f"Markdown destination changed to a non-file before writing: {path}"
            )
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise SemanticError(f"Markdown destination changed before writing: {path}")
        os.ftruncate(descriptor, 0)
        view = memoryview(raw)
        written = 0
        while written < len(raw):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("bounded Markdown write made no progress")
            written += count
        after = os.fstat(descriptor)
        if (
            not stat.S_ISREG(after.st_mode)
            or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
            or after.st_size != len(raw)
        ):
            raise SemanticError(
                f"Markdown destination changed while being written: {path}"
            )
    except SemanticError:
        raise
    except (OSError, ValueError, RecursionError) as exc:
        raise SemanticError(
            f"Markdown destination cannot be written safely: "
            f"{path}: {_exception_text(exc)}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _load_json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="strict")
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > PROFILE_JSON_MAX_DEPTH:
                raise ValueError(
                    f"{label} JSON nesting exceeds {PROFILE_JSON_MAX_DEPTH} levels"
                )
        elif character in "]}":
            depth -= 1
    document = json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(document, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return document


def _read_exact_regular_file(
    path: Path,
    *,
    expected_bytes: int,
    label: str,
) -> tuple[bytes | None, list[str]]:
    """Read one regular file with lstat/fstat checks and a strict byte ceiling."""
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None, [f"{label} is missing: {path}"]
    except (OSError, ValueError, RecursionError) as exc:
        return None, [f"{label} cannot be inspected: {_exception_text(exc)}"]
    if stat.S_ISLNK(before.st_mode):
        return None, [f"{label} must not be a symlink: {path}"]
    if not stat.S_ISREG(before.st_mode):
        return None, [f"{label} is not a regular file: {path}"]
    if before.st_size != expected_bytes:
        return None, [
            f"{label} byte size {before.st_size} differs from expected {expected_bytes}"
        ]

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            return None, [f"{label} changed to a non-file while being verified"]
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            return None, [f"{label} changed while being verified"]
        if opened.st_size != expected_bytes:
            return None, [
                f"{label} byte size changed while being verified: "
                f"{opened.st_size} != {expected_bytes}"
            ]
        remaining = expected_bytes + 1
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    except (OSError, ValueError, RecursionError) as exc:
        return None, [f"{label} cannot be read: {_exception_text(exc)}"]
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if len(raw) != expected_bytes:
        return None, [
            f"{label} bounded read returned {len(raw)} bytes; expected {expected_bytes}"
        ]
    return raw, []


def _path_chain_errors(
    repository_root: Path,
    target: Path,
    *,
    label: str,
) -> list[str]:
    """Reject symlinks and non-directory parents without resolving the path."""
    if not repository_root.is_absolute() or ".." in repository_root.parts:
        return ["repository root must be an absolute path without parent traversal"]
    try:
        relative = target.relative_to(repository_root)
    except ValueError:
        return [f"{label} must be inside the repository root"]
    components = (repository_root,)
    if relative.parts:
        components += tuple(
            repository_root.joinpath(*relative.parts[:index])
            for index in range(1, len(relative.parts) + 1)
        )
    for index, component in enumerate(components):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            return [f"{label} path component is missing: {component}"]
        except (OSError, ValueError, RecursionError) as exc:
            return [
                f"{label} path component cannot be inspected: "
                f"{component}: {_exception_text(exc)}"
            ]
        if stat.S_ISLNK(metadata.st_mode):
            return [f"{label} path component must not be a symlink: {component}"]
        if index < len(components) - 1 and not stat.S_ISDIR(metadata.st_mode):
            return [f"{label} parent path component is not a directory: {component}"]
    return []


def _inventory_name_error(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return "must be a non-empty string"
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
        return "must not contain control characters or lone surrogates"
    if not value.isascii() or any(
        not (character.isalnum() or character in "._-") for character in value
    ):
        return "must use only conservative ASCII filename characters"
    if value in {".", ".."} or "/" in value or "\\" in value:
        return "must be a flat profile-relative filename"
    return None


def _verify_profile_vendor(
    *,
    repository_root: Path,
    profile_root: Path,
    lock_path: Path,
) -> ProfileVendorVerification:
    errors: list[str] = []
    expected_profile_root = repository_root / "profiles" / "bundle-wiki" / "v1"
    expected_lock_path = repository_root / "profiles" / "bundle-wiki" / "v1.vendor-lock.json"
    if profile_root != expected_profile_root:
        errors.append(
            "vendored profile root must be the exact repository profile path: "
            f"{expected_profile_root}"
        )
    if lock_path != expected_lock_path:
        errors.append(
            "profile vendor lock must be the exact repository lock path: "
            f"{expected_lock_path}"
        )
    if errors:
        return ProfileVendorVerification(tuple(errors))
    errors.extend(_path_chain_errors(repository_root, lock_path, label="profile vendor lock"))
    errors.extend(_path_chain_errors(repository_root, profile_root, label="vendored profile"))
    if errors:
        return ProfileVendorVerification(tuple(errors))
    raw_lock, read_errors = _read_exact_regular_file(
        lock_path,
        expected_bytes=PROFILE_VENDOR_LOCK_BYTES,
        label="profile vendor lock",
    )
    if read_errors or raw_lock is None:
        return ProfileVendorVerification(tuple(read_errors))
    lock_digest = hashlib.sha256(raw_lock).hexdigest()
    if lock_digest != PROFILE_VENDOR_LOCK_SHA256:
        return ProfileVendorVerification(
            (
                "profile vendor lock SHA-256 "
                f"{lock_digest} differs from approved {PROFILE_VENDOR_LOCK_SHA256}",
            )
        )
    try:
        lock = _load_json_object(raw_lock, label="profile vendor lock")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        return ProfileVendorVerification(
            (f"profile vendor lock is not valid strict UTF-8 JSON: {_exception_text(exc)}",)
        )

    expected_keys = {"schema", "profile", "release", "file_count", "identity", "files"}
    actual_keys = set(lock)
    for key in sorted(expected_keys - actual_keys):
        errors.append(f"profile vendor lock is missing top-level field: {key}")
    for key in sorted(actual_keys - expected_keys):
        errors.append(f"profile vendor lock has unexpected top-level field: {key}")
    if lock.get("schema") != PROFILE_VENDOR_LOCK_SCHEMA:
        errors.append(
            "profile vendor lock schema must be " + PROFILE_VENDOR_LOCK_SCHEMA
        )
    if lock.get("profile") != PROFILE_URL:
        errors.append("profile vendor lock has the wrong canonical profile identity")

    release = lock.get("release")
    if not isinstance(release, dict):
        errors.append("profile vendor lock release must be an object")
    else:
        for key, expected in PROFILE_VENDOR_RELEASE.items():
            if release.get(key) != expected:
                errors.append(
                    f"profile vendor lock release.{key} differs from approved {expected}"
                )
        for key in sorted(set(release) - set(PROFILE_VENDOR_RELEASE)):
            errors.append(f"profile vendor lock release has unexpected field: {key}")

    file_count = lock.get("file_count")
    if isinstance(file_count, bool) or not isinstance(file_count, int):
        errors.append("profile vendor lock file_count must be an integer")
    elif file_count != PROFILE_VENDOR_FILE_COUNT:
        errors.append(
            "profile vendor lock file_count "
            f"{file_count} differs from approved {PROFILE_VENDOR_FILE_COUNT}"
        )

    identity = lock.get("identity")
    identity_sha: str | None = None
    if not isinstance(identity, dict):
        errors.append("profile vendor lock identity must be an object")
    else:
        identity_keys = {"algorithm", "canonicalisation", "sha256"}
        for key in sorted(identity_keys - set(identity)):
            errors.append(f"profile vendor lock identity is missing field: {key}")
        for key in sorted(set(identity) - identity_keys):
            errors.append(f"profile vendor lock identity has unexpected field: {key}")
        if identity.get("algorithm") != PROFILE_VENDOR_IDENTITY_ALGORITHM:
            errors.append("profile vendor lock identity algorithm must be sha256")
        if (
            identity.get("canonicalisation")
            != PROFILE_VENDOR_IDENTITY_CANONICALISATION
        ):
            errors.append("profile vendor lock has the wrong identity canonicalisation")
        if not _is_sha256(identity.get("sha256")):
            errors.append("profile vendor lock identity.sha256 must be lowercase SHA-256")
        else:
            identity_sha = identity["sha256"]

    files = lock.get("files")
    rows: list[tuple[str, int, str]] = []
    if not isinstance(files, list):
        errors.append("profile vendor lock files must be an array")
        files = []
    elif len(files) != PROFILE_VENDOR_FILE_COUNT:
        errors.append(
            "profile vendor lock inventory contains "
            f"{len(files)} entries; expected {PROFILE_VENDOR_FILE_COUNT}"
        )
    if isinstance(file_count, int) and not isinstance(file_count, bool):
        if len(files) != file_count:
            errors.append(
                "profile vendor lock file_count does not match its inventory length"
            )

    for index, entry in enumerate(files):
        label = f"profile vendor lock files[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        entry_keys = {"path", "bytes", "sha256"}
        for key in sorted(entry_keys - set(entry)):
            errors.append(f"{label} is missing field: {key}")
        for key in sorted(set(entry) - entry_keys):
            errors.append(f"{label} has unexpected field: {key}")
        path = entry.get("path")
        byte_count = entry.get("bytes")
        digest = entry.get("sha256")
        valid = True
        name_error = _inventory_name_error(path)
        if name_error:
            errors.append(f"{label}.path {name_error}")
            valid = False
        if (
            isinstance(byte_count, bool)
            or not isinstance(byte_count, int)
            or byte_count < 0
            or byte_count > PROFILE_VENDOR_MAX_FILE_BYTES
        ):
            errors.append(
                f"{label}.bytes must be an integer from 0 to "
                f"{PROFILE_VENDOR_MAX_FILE_BYTES}"
            )
            valid = False
        if not _is_sha256(digest):
            errors.append(f"{label}.sha256 must be lowercase SHA-256")
            valid = False
        if valid:
            assert isinstance(path, str)
            assert isinstance(byte_count, int)
            assert isinstance(digest, str)
            rows.append((path, byte_count, digest))

    paths = [row[0] for row in rows]
    if len(paths) != len(set(paths)):
        errors.append("profile vendor lock inventory paths must be unique")
    if paths != sorted(paths):
        errors.append("profile vendor lock inventory paths must be in lexical order")
    if tuple(paths) != PROFILE_VENDOR_FILES:
        errors.append("profile vendor lock inventory names differ from the approved exact set")
    if len(rows) == len(files) and identity_sha is not None:
        declared_identity = _profile_identity(rows)
        if declared_identity != identity_sha:
            errors.append(
                "profile vendor lock declared inventory identity "
                f"{declared_identity} differs from {identity_sha}"
            )
    if errors:
        return ProfileVendorVerification(tuple(errors))

    try:
        actual_names: list[str] = []
        with os.scandir(profile_root) as entries:
            for entry in entries:
                actual_names.append(entry.name)
                if len(actual_names) > PROFILE_VENDOR_FILE_COUNT:
                    return ProfileVendorVerification(
                        (
                            "vendored profile contains more than the approved "
                            f"{PROFILE_VENDOR_FILE_COUNT} entries; enumeration stopped",
                        )
                    )
    except (OSError, ValueError, RecursionError) as exc:
        return ProfileVendorVerification(
            (f"vendored profile cannot be enumerated: {_exception_text(exc)}",)
        )
    for name in actual_names:
        name_error = _inventory_name_error(name)
        if name_error:
            errors.append(f"vendored profile entry {name!r} {name_error}")
    expected_names = set(PROFILE_VENDOR_FILES)
    actual_name_set = set(actual_names)
    for name in sorted(expected_names - actual_name_set):
        errors.append(f"vendored profile file is missing: {name}")
    for name in sorted(actual_name_set - expected_names):
        errors.append(f"vendored profile contains unexpected entry: {name!r}")
    if errors:
        return ProfileVendorVerification(tuple(errors))

    expected = {path: (byte_count, digest) for path, byte_count, digest in rows}
    actual_rows: list[tuple[str, int, str]] = []
    verified_files: dict[str, bytes] = {}
    for path, (expected_bytes, expected_digest) in sorted(expected.items()):
        raw, file_errors = _read_exact_regular_file(
            profile_root / path,
            expected_bytes=expected_bytes,
            label=f"vendored profile file {path}",
        )
        if file_errors or raw is None:
            errors.extend(file_errors)
            continue
        digest = hashlib.sha256(raw).hexdigest()
        actual_rows.append((path, len(raw), digest))
        if digest != expected_digest:
            errors.append(
                f"vendored profile file SHA-256 differs for {path}: "
                f"{digest} != {expected_digest}"
            )
        else:
            verified_files[path] = raw
    if len(actual_rows) == len(expected) and identity_sha is not None:
        actual_identity = _profile_identity(actual_rows)
        if actual_identity != identity_sha:
            errors.append(
                "vendored profile aggregate identity "
                f"{actual_identity} differs from {identity_sha}"
            )
    if errors:
        return ProfileVendorVerification(tuple(errors))
    return ProfileVendorVerification((), verified_files)


def verify_profile_vendor(
    *,
    repository_root: Path | None = None,
    profile_root: Path | None = None,
    lock_path: Path | None = None,
) -> ProfileVendorVerification:
    """Fail-closed wrapper for the complete, bounded profile verification."""
    repository_root = ROOT if repository_root is None else repository_root
    profile_root = PROFILE_ROOT if profile_root is None else profile_root
    lock_path = PROFILE_VENDOR_LOCK_PATH if lock_path is None else lock_path
    try:
        return _verify_profile_vendor(
            repository_root=repository_root,
            profile_root=profile_root,
            lock_path=lock_path,
        )
    except (OSError, ValueError, RecursionError) as exc:
        return ProfileVendorVerification(
            (f"profile vendor verification failed closed: {_exception_text(exc)}",)
        )


def profile_vendor_lock_errors(
    *,
    repository_root: Path | None = None,
    profile_root: Path | None = None,
    lock_path: Path | None = None,
) -> list[str]:
    """Return errors from the complete local Bundle Wiki profile verification."""
    return list(
        verify_profile_vendor(
            repository_root=repository_root,
            profile_root=profile_root,
            lock_path=lock_path,
        ).errors
    )


def verify_semantic_assertion_schema(
    *,
    repository_root: Path | None = None,
    profile_root: Path | None = None,
    lock_path: Path | None = None,
) -> SemanticAssertionSchemaVerification:
    """Return the exact schema bytes and object from one verified profile read."""
    profile = verify_profile_vendor(
        repository_root=repository_root,
        profile_root=profile_root,
        lock_path=lock_path,
    )
    if profile.errors or profile.files is None:
        return SemanticAssertionSchemaVerification(profile.errors)
    raw = profile.files.get("semantic-assertion.schema.json")
    if raw is None:
        return SemanticAssertionSchemaVerification(
            ("verified profile did not retain semantic-assertion.schema.json",)
        )
    if len(raw) != SEMANTIC_ASSERTION_SCHEMA_BYTES:
        return SemanticAssertionSchemaVerification(
            (
                "semantic assertion schema byte size "
                f"{len(raw)} differs from pinned {SEMANTIC_ASSERTION_SCHEMA_BYTES}",
            )
        )
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SEMANTIC_ASSERTION_SCHEMA_SHA256:
        return SemanticAssertionSchemaVerification(
            (
                "semantic assertion schema SHA-256 "
                f"{digest} differs from pinned {SEMANTIC_ASSERTION_SCHEMA_SHA256}",
            )
        )
    try:
        schema = _load_json_object(raw, label="semantic assertion schema")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        return SemanticAssertionSchemaVerification(
            (f"semantic assertion schema is not valid strict UTF-8 JSON: {_exception_text(exc)}",)
        )
    errors: list[str] = []
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("semantic assertion schema is not Draft 2020-12")
    if schema.get("$id") != SEMANTIC_ASSERTION_SCHEMA_ID:
        errors.append("semantic assertion schema has the wrong canonical $id")
    if errors:
        return SemanticAssertionSchemaVerification(tuple(errors))
    return SemanticAssertionSchemaVerification((), raw, schema)


def semantic_assertion_schema_pin_errors() -> list[str]:
    """Prove the producer is using the exact reviewed shared schema bytes."""
    try:
        return list(verify_semantic_assertion_schema().errors)
    except (OSError, ValueError, RecursionError) as exc:
        return [f"semantic assertion schema verification failed closed: {_exception_text(exc)}"]


def semantic_assertion_schema_validator(
) -> tuple[list[str], Draft202012Validator | None]:
    """Build a validator from the schema object retained by the verified read."""
    try:
        verification = verify_semantic_assertion_schema()
        errors = list(verification.errors)
        if errors or verification.schema is None:
            return errors, None
        return [], Draft202012Validator(
            verification.schema,
            format_checker=FormatChecker(),
        )
    except (OSError, ValueError, RecursionError) as exc:
        return [
            "semantic assertion schema validator failed closed: "
            + _exception_text(exc)
        ], None


def schema_validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name), format_checker=FormatChecker())


def validator_errors(
    document: dict[str, Any], validator: Draft202012Validator
) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(
            validator.iter_errors(document), key=lambda item: list(item.absolute_path)
        )
    ]


def schema_errors(document: dict[str, Any], schema_name: str) -> list[str]:
    return validator_errors(document, schema_validator(schema_name))


def pinned_document_loader(extra: dict[str, Any] | None = None) -> Callable[[str, dict[str, Any] | None], dict[str, Any]]:
    contexts: dict[str, Any] = {
        CONTEXT_URL: json.loads(CONTEXT_PATH.read_text(encoding="utf-8")),
        SEMANTIC_CONTEXT_URL: json.loads(SEMANTIC_CONTEXT_PATH.read_text(encoding="utf-8")),
    }
    contexts.update(extra or {})

    def load(url: str, _options: dict[str, Any] | None = None) -> dict[str, Any]:
        if url not in contexts:
            raise SemanticError(f"remote JSON-LD context is not allowlisted: {url}")
        return {
            "contextUrl": None,
            "documentUrl": url,
            "document": contexts[url],
            "contentType": "application/ld+json",
        }

    return load


def expand(document: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return jsonld.expand(document, options={"documentLoader": pinned_document_loader()})
    except Exception as exc:
        raise SemanticError(f"JSON-LD expansion failed: {exc}") from exc


def compact(document: dict[str, Any]) -> dict[str, Any]:
    try:
        return jsonld.compact(
            expand(document),
            CONTEXT_URL,
            options={"documentLoader": pinned_document_loader(), "compactArrays": False},
        )
    except Exception as exc:
        raise SemanticError(f"JSON-LD compaction failed: {exc}") from exc


def semantic_json(document: dict[str, Any]) -> str:
    return json.dumps(compact(document), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
