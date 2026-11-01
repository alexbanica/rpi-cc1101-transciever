#!/usr/bin/env python3
"""Credential-free preflight for the exact package pair before twine upload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

try:
    from .package_artifacts import validate_artifacts
    from .release_version import parse_release_tag
except ImportError:  # direct script execution
    from package_artifacts import validate_artifacts
    from release_version import parse_release_tag


def preflight(tag: str, artifact_dir, commit=None):
    directory = Path(artifact_dir)
    artifacts = validate_artifacts(tag, directory)
    manifest_path = directory / "provenance.json"
    if not manifest_path.is_file():
        raise ValueError("provenance.json is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if set(manifest) != {"event_commit", "tag", "version", "artifacts"}:
        raise ValueError("provenance manifest has unexpected fields")
    if manifest["tag"] != tag or manifest["version"] != parse_release_tag(tag):
        raise ValueError("provenance tag/version mismatch")
    if not re.fullmatch(r"[0-9a-f]{40,64}", manifest["event_commit"]):
        raise ValueError("provenance event_commit is invalid")
    if commit is not None and manifest["event_commit"] != commit.lower():
        raise ValueError("provenance event commit mismatch")
    expected = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts}
    if manifest["artifacts"] != expected:
        raise ValueError("artifact hashes do not match provenance manifest")
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    if actual_files != set(expected) | {"provenance.json"}:
        raise ValueError("artifact directory contains unexpected files")
    return artifacts


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG"))
    parser.add_argument("--artifacts", default="dist")
    parser.add_argument("--commit")
    args = parser.parse_args(argv)
    if not args.tag:
        parser.error("--tag or RELEASE_TAG is required")
    try:
        for path in preflight(args.tag, args.artifacts, args.commit):
            print(path)
    except (ValueError, json.JSONDecodeError) as error:
        print(f"publication preflight failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
