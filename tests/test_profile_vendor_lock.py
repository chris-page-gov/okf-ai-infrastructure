from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import okf_semantic  # noqa: E402
import semantic_projection  # noqa: E402


PROFILE_FILES = okf_semantic.PROFILE_VENDOR_FILES


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aggregate_identity(files: list[dict[str, object]]) -> str:
    canonical = "".join(
        f"{entry['path']}\t{entry['bytes']}\t{entry['sha256']}\n"
        for entry in sorted(files, key=lambda item: str(item["path"]))
    ).encode("utf-8")
    return sha256(canonical)


def write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def build_fixture(base: Path) -> tuple[Path, Path, dict[str, object]]:
    profile_root = base / "profiles" / "bundle-wiki" / "v1"
    profile_root.mkdir(parents=True)
    inventory: list[dict[str, object]] = []
    for index, name in enumerate(PROFILE_FILES):
        raw = f"canonical fixture {index}: {name}\n".encode()
        (profile_root / name).write_bytes(raw)
        inventory.append({"path": name, "bytes": len(raw), "sha256": sha256(raw)})
    lock: dict[str, object] = {
        "schema": okf_semantic.PROFILE_VENDOR_LOCK_SCHEMA,
        "profile": okf_semantic.PROFILE_URL,
        "release": copy.deepcopy(okf_semantic.PROFILE_VENDOR_RELEASE),
        "file_count": len(inventory),
        "identity": {
            "algorithm": okf_semantic.PROFILE_VENDOR_IDENTITY_ALGORITHM,
            "canonicalisation": okf_semantic.PROFILE_VENDOR_IDENTITY_CANONICALISATION,
            "sha256": aggregate_identity(inventory),
        },
        "files": inventory,
    }
    lock_path = profile_root.parent / "v1.vendor-lock.json"
    write_json(lock_path, lock)
    return profile_root, lock_path, lock


def fixture_repository(profile_root: Path) -> Path:
    return profile_root.parents[2]


def fixture_errors(profile_root: Path, lock_path: Path) -> list[str]:
    raw_lock = lock_path.read_bytes()
    with (
        mock.patch.object(
            okf_semantic, "PROFILE_VENDOR_LOCK_SHA256", sha256(raw_lock)
        ),
        mock.patch.object(
            okf_semantic, "PROFILE_VENDOR_LOCK_BYTES", len(raw_lock)
        ),
    ):
        return okf_semantic.profile_vendor_lock_errors(
            repository_root=fixture_repository(profile_root),
            profile_root=profile_root,
            lock_path=lock_path,
        )


def verify_lock_bytes(
    profile_root: Path,
    lock_path: Path,
    raw_lock: bytes,
) -> okf_semantic.ProfileVendorVerification:
    lock_path.write_bytes(raw_lock)
    with (
        mock.patch.object(
            okf_semantic, "PROFILE_VENDOR_LOCK_SHA256", sha256(raw_lock)
        ),
        mock.patch.object(
            okf_semantic, "PROFILE_VENDOR_LOCK_BYTES", len(raw_lock)
        ),
    ):
        return okf_semantic.verify_profile_vendor(
            repository_root=fixture_repository(profile_root),
            profile_root=profile_root,
            lock_path=lock_path,
        )


class ProfileVendorLockTest(unittest.TestCase):
    def test_approved_explorer_release_inventory_and_schema_pins_are_exact(self) -> None:
        self.assertEqual(3_281, okf_semantic.PROFILE_VENDOR_LOCK_BYTES)
        self.assertEqual(
            "979af714974abb093ac9d4b1b7e289597c61d33c24bb6959d9914c2f74dc6a09",
            okf_semantic.PROFILE_VENDOR_LOCK_SHA256,
        )
        self.assertEqual(16, okf_semantic.PROFILE_VENDOR_FILE_COUNT)
        self.assertEqual(PROFILE_FILES, tuple(sorted(PROFILE_FILES)))
        self.assertEqual(
            {
                "repository": "https://github.com/chris-page-gov/okf-explorer",
                "version": "0.6.0",
                "tag": "v0.6.0",
                "tag_object": "d256a74419c2593c2bf2f3f5749c606fad5daf9d",
                "commit": "4bb7b92a64b7ba69bde9b1e86786217338cd166d",
                "git_tree": "d26ae9a818041ff74c469e653ec714632ddbfc2a",
            },
            okf_semantic.PROFILE_VENDOR_RELEASE,
        )
        self.assertEqual(7_308, okf_semantic.SEMANTIC_ASSERTION_SCHEMA_BYTES)
        self.assertEqual(
            "f69480328db4b64d678d9c50b6534d808000f7fb50a30e8cc9e3bf2facbcb8bc",
            okf_semantic.SEMANTIC_ASSERTION_SCHEMA_SHA256,
        )

    def test_complete_flat_fixture_matches_its_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_root, lock_path, _ = build_fixture(Path(directory))
            self.assertEqual([], fixture_errors(profile_root, lock_path))

    def test_lock_size_and_digest_fail_before_open_or_json_parse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_root, lock_path, _ = build_fixture(Path(directory))
            raw_lock = lock_path.read_bytes()
            with (
                mock.patch.object(
                    okf_semantic, "PROFILE_VENDOR_LOCK_BYTES", len(raw_lock) + 1
                ),
                mock.patch.object(os, "open", side_effect=AssertionError("must not open")),
            ):
                result = okf_semantic.verify_profile_vendor(
                    repository_root=fixture_repository(profile_root),
                    profile_root=profile_root,
                    lock_path=lock_path,
                )
            self.assertTrue(any("byte size" in error for error in result.errors))

            with (
                mock.patch.object(
                    okf_semantic, "PROFILE_VENDOR_LOCK_BYTES", len(raw_lock)
                ),
                mock.patch.object(okf_semantic, "PROFILE_VENDOR_LOCK_SHA256", "0" * 64),
                mock.patch.object(
                    okf_semantic,
                    "_load_json_object",
                    side_effect=AssertionError("digest mismatch must stop parsing"),
                ),
            ):
                result = okf_semantic.verify_profile_vendor(
                    repository_root=fixture_repository(profile_root),
                    profile_root=profile_root,
                    lock_path=lock_path,
                )
            self.assertEqual(1, len(result.errors))
            self.assertIn("SHA-256", result.errors[0])

    def test_lock_json_rejects_non_object_duplicate_keys_and_excessive_nesting(self) -> None:
        cases = {
            "non-object": (b"[]", "JSON root must be an object"),
            "duplicate": (b'{"schema":"one","schema":"two"}', "duplicate JSON object key"),
            "recursive": (
                (b'{"nested":' + b"[" * 1_100 + b"0" + b"]" * 1_100 + b"}"),
                "JSON nesting exceeds",
            ),
        }
        for label, (raw, expected) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                profile_root, lock_path, _ = build_fixture(Path(directory))
                result = verify_lock_bytes(profile_root, lock_path, raw)
                self.assertTrue(
                    any(expected in error for error in result.errors), result.errors
                )

    def test_lock_header_release_and_identity_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_root, lock_path, lock = build_fixture(Path(directory))
            lock["schema"] = "unrecognised-lock-schema"
            lock["profile"] = "https://example.test/wrong-profile/"
            assert isinstance(lock["release"], dict)
            lock["release"]["tag_object"] = "0" * 40
            assert isinstance(lock["identity"], dict)
            lock["identity"]["algorithm"] = "sha1"
            lock["identity"]["sha256"] = "1" * 64
            write_json(lock_path, lock)
            errors = fixture_errors(profile_root, lock_path)
            self.assertTrue(any("schema must be" in error for error in errors), errors)
            self.assertTrue(any("canonical profile identity" in error for error in errors), errors)
            self.assertTrue(any("release.tag_object" in error for error in errors), errors)
            self.assertTrue(any("algorithm must be sha256" in error for error in errors), errors)
            self.assertTrue(any("declared inventory identity" in error for error in errors), errors)

    def test_inventory_requires_sixteen_unique_sorted_exact_rows(self) -> None:
        cases = {
            "wrong count": lambda lock: lock.__setitem__("file_count", 15),
            "duplicate path": lambda lock: lock["files"][1].__setitem__(
                "path", lock["files"][0]["path"]
            ),
            "unsorted rows": lambda lock: lock["files"].__setitem__(
                slice(0, 2), reversed(lock["files"][0:2])
            ),
            "safe but unapproved": lambda lock: lock["files"][0].__setitem__(
                "path", "alternative.schema.json"
            ),
        }
        expected = {
            "wrong count": "differs from approved 16",
            "duplicate path": "paths must be unique",
            "unsorted rows": "lexical order",
            "safe but unapproved": "approved exact set",
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                profile_root, lock_path, lock = build_fixture(Path(directory))
                mutate(lock)
                write_json(lock_path, lock)
                errors = fixture_errors(profile_root, lock_path)
                self.assertTrue(any(expected[label] in error for error in errors), errors)

    def test_inventory_names_reject_controls_and_lone_surrogates(self) -> None:
        for label, bad_name in (
            ("control", "bad\u0001name.json"),
            ("surrogate", "bad\ud800name.json"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                profile_root, lock_path, lock = build_fixture(Path(directory))
                lock["files"][0]["path"] = bad_name
                write_json(lock_path, lock)
                errors = fixture_errors(profile_root, lock_path)
                self.assertTrue(
                    any("control characters or lone surrogates" in error for error in errors),
                    errors,
                )

    def test_profile_inventory_rejects_missing_extra_symlink_non_file_and_drift(self) -> None:
        def missing(profile_root: Path) -> None:
            (profile_root / PROFILE_FILES[0]).unlink()

        def extra(profile_root: Path) -> None:
            (profile_root / "unlocked.json").write_text("{}\n", encoding="utf-8")

        def symlink(profile_root: Path) -> None:
            target = profile_root / PROFILE_FILES[0]
            target.unlink()
            target.symlink_to(PROFILE_FILES[1])

        def non_file(profile_root: Path) -> None:
            target = profile_root / PROFILE_FILES[0]
            target.unlink()
            target.mkdir()

        def drift(profile_root: Path) -> None:
            target = profile_root / PROFILE_FILES[0]
            raw = target.read_bytes()
            target.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])

        cases = {
            "missing": (missing, "file is missing"),
            "extra": (extra, "enumeration stopped"),
            "symlink": (symlink, "must not be a symlink"),
            "non-file": (non_file, "not a regular file"),
            "drift": (drift, "file SHA-256 differs"),
        }
        for label, (mutate, expected) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                profile_root, lock_path, _ = build_fixture(Path(directory))
                mutate(profile_root)
                errors = fixture_errors(profile_root, lock_path)
                self.assertTrue(any(expected in error for error in errors), errors)
                if label == "drift":
                    self.assertTrue(
                        any("aggregate identity" in error for error in errors), errors
                    )

    def test_every_repository_to_profile_path_component_must_be_non_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real_repository = base / "real"
            profile_root, lock_path, _ = build_fixture(real_repository)

            linked_repository = base / "linked-repository"
            linked_repository.symlink_to(real_repository.name, target_is_directory=True)
            linked_profile = linked_repository / "profiles" / "bundle-wiki" / "v1"
            linked_lock = linked_profile.parent / "v1.vendor-lock.json"
            result = okf_semantic.verify_profile_vendor(
                repository_root=linked_repository,
                profile_root=linked_profile,
                lock_path=linked_lock,
            )
            self.assertTrue(any("must not be a symlink" in error for error in result.errors))

            intermediate_repository = base / "linked-component"
            intermediate_repository.mkdir()
            (intermediate_repository / "profiles").symlink_to(
                real_repository / "profiles", target_is_directory=True
            )
            intermediate_profile = (
                intermediate_repository / "profiles" / "bundle-wiki" / "v1"
            )
            intermediate_lock = intermediate_profile.parent / "v1.vendor-lock.json"
            result = okf_semantic.verify_profile_vendor(
                repository_root=intermediate_repository,
                profile_root=intermediate_profile,
                lock_path=intermediate_lock,
            )
            self.assertTrue(any("must not be a symlink" in error for error in result.errors))

            real_profile = profile_root.with_name("v1-real")
            profile_root.rename(real_profile)
            profile_root.symlink_to(real_profile.name, target_is_directory=True)
            result = okf_semantic.verify_profile_vendor(
                repository_root=real_repository,
                profile_root=profile_root,
                lock_path=lock_path,
            )
            self.assertTrue(any("must not be a symlink" in error for error in result.errors))
            profile_root.unlink()
            real_profile.rename(profile_root)

            real_lock = lock_path.with_suffix(".real.json")
            lock_path.rename(real_lock)
            lock_path.symlink_to(real_lock.name)
            result = okf_semantic.verify_profile_vendor(
                repository_root=real_repository,
                profile_root=profile_root,
                lock_path=lock_path,
            )
            self.assertTrue(any("must not be a symlink" in error for error in result.errors))

    def test_lstat_size_precheck_and_read_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bounded.bin"
            path.write_bytes(b"abcd")
            with mock.patch.object(os, "open", side_effect=AssertionError("must not open")):
                raw, errors = okf_semantic._read_exact_regular_file(
                    path, expected_bytes=3, label="fixture"
                )
            self.assertIsNone(raw)
            self.assertTrue(any("byte size" in error for error in errors), errors)

            requested: list[int] = []
            real_read = os.read

            def recording_read(descriptor: int, size: int) -> bytes:
                requested.append(size)
                return real_read(descriptor, size)

            with mock.patch.object(os, "read", side_effect=recording_read):
                raw, errors = okf_semantic._read_exact_regular_file(
                    path, expected_bytes=4, label="fixture"
                )
            self.assertEqual(b"abcd", raw)
            self.assertEqual([], errors)
            self.assertTrue(requested)
            self.assertLessEqual(max(requested), 5)

    def test_value_and_recursion_failures_return_errors(self) -> None:
        for exception in (ValueError("bad value"), RecursionError("too deep")):
            with self.subTest(exception=type(exception).__name__), mock.patch.object(
                okf_semantic, "_verify_profile_vendor", side_effect=exception
            ):
                result = okf_semantic.verify_profile_vendor()
                self.assertTrue(any("failed closed" in error for error in result.errors))
            with mock.patch.object(
                okf_semantic, "verify_semantic_assertion_schema", side_effect=exception
            ):
                errors = okf_semantic.semantic_assertion_schema_pin_errors()
                self.assertTrue(any("failed closed" in error for error in errors))
            with mock.patch.object(
                okf_semantic, "verify_semantic_assertion_schema", side_effect=exception
            ):
                errors, validator = okf_semantic.semantic_assertion_schema_validator()
                self.assertIsNone(validator)
                self.assertTrue(any("failed closed" in error for error in errors))

    def test_schema_digest_stops_parsing_and_strict_json_rejects_bad_roots(self) -> None:
        bad_schema = b"[]"
        profile = okf_semantic.ProfileVendorVerification(
            (), {"semantic-assertion.schema.json": bad_schema}
        )
        with (
            mock.patch.object(okf_semantic, "verify_profile_vendor", return_value=profile),
            mock.patch.object(okf_semantic, "SEMANTIC_ASSERTION_SCHEMA_BYTES", 2),
            mock.patch.object(okf_semantic, "SEMANTIC_ASSERTION_SCHEMA_SHA256", "0" * 64),
            mock.patch.object(
                okf_semantic,
                "_load_json_object",
                side_effect=AssertionError("digest mismatch must stop parsing"),
            ),
        ):
            result = okf_semantic.verify_semantic_assertion_schema()
        self.assertEqual(1, len(result.errors))
        self.assertIn("SHA-256", result.errors[0])

        cases = {
            "non-object": (b"[]", "JSON root must be an object"),
            "duplicate": (
                b'{"$schema":"one","$schema":"two"}',
                "duplicate JSON object key",
            ),
            "recursive": (
                b'{"nested":' + b"[" * 1_100 + b"0" + b"]" * 1_100 + b"}",
                "JSON nesting exceeds",
            ),
        }
        for label, (raw, expected) in cases.items():
            with self.subTest(label=label):
                profile = okf_semantic.ProfileVendorVerification(
                    (), {"semantic-assertion.schema.json": raw}
                )
                with (
                    mock.patch.object(
                        okf_semantic, "verify_profile_vendor", return_value=profile
                    ),
                    mock.patch.object(
                        okf_semantic, "SEMANTIC_ASSERTION_SCHEMA_BYTES", len(raw)
                    ),
                    mock.patch.object(
                        okf_semantic, "SEMANTIC_ASSERTION_SCHEMA_SHA256", sha256(raw)
                    ),
                ):
                    result = okf_semantic.verify_semantic_assertion_schema()
                self.assertTrue(
                    any(expected in error for error in result.errors), result.errors
                )

    def test_schema_object_is_reused_without_reopening_profile_file(self) -> None:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": okf_semantic.SEMANTIC_ASSERTION_SCHEMA_ID,
            "type": "object",
        }
        raw = json.dumps(schema).encode()
        profile = okf_semantic.ProfileVendorVerification(
            (), {"semantic-assertion.schema.json": raw}
        )
        with (
            mock.patch.object(okf_semantic, "verify_profile_vendor", return_value=profile),
            mock.patch.object(
                okf_semantic, "SEMANTIC_ASSERTION_SCHEMA_BYTES", len(raw)
            ),
            mock.patch.object(
                okf_semantic, "SEMANTIC_ASSERTION_SCHEMA_SHA256", sha256(raw)
            ),
            mock.patch.object(
                Path, "read_bytes", side_effect=AssertionError("must not reopen schema")
            ),
        ):
            verification = okf_semantic.verify_semantic_assertion_schema()
        self.assertEqual((), verification.errors)
        self.assertIs(raw, verification.raw)
        self.assertEqual(schema, verification.schema)

        with (
            mock.patch.object(
                okf_semantic,
                "verify_semantic_assertion_schema",
                return_value=verification,
            ),
            mock.patch.object(
                Path, "read_bytes", side_effect=AssertionError("must not reopen schema")
            ),
        ):
            self.assertEqual([], okf_semantic.semantic_assertion_schema_pin_errors())

        with (
            mock.patch.object(
                okf_semantic,
                "verify_semantic_assertion_schema",
                return_value=verification,
            ),
            mock.patch.object(
                okf_semantic,
                "load_schema",
                side_effect=AssertionError("must not call load_schema"),
            ),
        ):
            errors, validator = okf_semantic.semantic_assertion_schema_validator()
        self.assertEqual([], errors)
        self.assertIsNotNone(validator)

    def test_relationship_validation_uses_verified_validator_not_schema_loader(self) -> None:
        validator = okf_semantic.Draft202012Validator({})
        bundle = {
            "corpora": {
                "ai-infrastructure-wiki": {"nodes": {}, "relationships": []}
            }
        }
        semantic = {"@graph": []}
        with (
            mock.patch.object(
                okf_semantic,
                "semantic_assertion_schema_validator",
                return_value=([], validator),
            ),
            mock.patch.object(
                okf_semantic,
                "schema_validator",
                side_effect=AssertionError("must not reopen schema"),
            ),
        ):
            errors = semantic_projection.validate_relationships(bundle, semantic)
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
