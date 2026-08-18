#!/usr/bin/env python3
"""Verify deployed Pages routes against the exact checked-out publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundle"
MAX_RESPONSE_BYTES = 16_000_000
IDENTITY_ROUTES = (
    "index.html",
    "okf-bundle.json",
    "semantic-validation.json",
)


def fetch_url(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
            "User-Agent": "okf-deployment-verifier/1",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 - reviewed HTTPS URL
        if response.status != 200:
            raise ValueError(f"{url} returned HTTP {response.status}")
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError(f"{url} exceeds the response limit")
    return data


def verify(
    base_url: str,
    fetcher: Callable[[str], bytes] = fetch_url,
) -> list[str]:
    """Return byte-identity errors for the checksum document and key routes."""

    if not base_url.startswith("https://"):
        return ["deployment base URL must use HTTPS"]
    base = base_url.rstrip("/") + "/"
    local_checksums = (BUNDLE / "checksums.json").read_bytes()
    try:
        remote_checksums = fetcher(urljoin(base, "checksums.json"))
    except (OSError, ValueError) as exc:
        return [f"checksums.json could not be fetched: {exc}"]
    errors: list[str] = []
    if remote_checksums != local_checksums:
        errors.append("deployed checksums.json differs from the validated commit")
    try:
        manifest = json.loads(local_checksums)
        files = manifest["files"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return [f"local checksums.json is invalid: {exc}"]
    for route in IDENTITY_ROUTES:
        expected = files.get(route)
        if not isinstance(expected, dict):
            errors.append(f"checksums.json does not bind {route}")
            continue
        try:
            deployed = fetcher(urljoin(base, route))
        except (OSError, ValueError) as exc:
            errors.append(f"{route} could not be fetched: {exc}")
            continue
        digest = hashlib.sha256(deployed).hexdigest()
        if digest != expected.get("sha256") or len(deployed) != expected.get("bytes"):
            errors.append(f"deployed {route} does not match its checksum entry")
        if deployed != (BUNDLE / route).read_bytes():
            errors.append(f"deployed {route} differs from the validated commit")
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OKF_DEPLOYMENT_URL"),
        help="Deployed Pages base URL; defaults to OKF_DEPLOYMENT_URL",
    )
    args = parser.parse_args(argv)
    if not args.base_url:
        parser.error("--base-url or OKF_DEPLOYMENT_URL is required")
    errors = verify(args.base_url)
    if errors:
        print("deployment verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "deployment verification passed: checksums.json and "
        f"{len(IDENTITY_ROUTES)} identity routes match the validated commit"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
