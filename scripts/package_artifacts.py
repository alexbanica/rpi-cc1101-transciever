#!/usr/bin/env python3
"""Build and validate a tagged wheel/sdist in an isolated source copy."""
import argparse
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.tags import Tag
from packaging.utils import parse_sdist_filename, parse_wheel_filename
from packaging.version import Version

try:
    from .release_version import parse_release_tag
except ImportError:  # direct script execution
    from release_version import parse_release_tag

DIST_NAME = "rpi-cc1101-transciever"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISHING_ENV = ("FORGEJO_PACKAGE_USERNAME", "FORGEJO_PACKAGE_TOKEN", "TWINE_USERNAME", "TWINE_PASSWORD")


def sanitized_environment():
    env = os.environ.copy()
    for key in PUBLISHING_ENV:
        env.pop(key, None)
    return env


def _metadata(path: Path) -> str:
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            files = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(files) != 1:
                raise ValueError(f"{path.name}: expected exactly one METADATA")
            return archive.read(files[0]).decode("utf-8")
    if path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as archive:
            files = [member for member in archive.getmembers() if member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")]
            if len(files) != 1:
                raise ValueError(f"{path.name}: expected exactly one PKG-INFO")
            stream = archive.extractfile(files[0])
            assert stream
            return stream.read().decode("utf-8")
    raise ValueError(f"unsupported distribution: {path.name}")


def validate_artifacts(tag: str, artifact_dir) -> list[Path]:
    expected_version = Version(parse_release_tag(tag))
    directory = Path(artifact_dir)
    entries = list(directory.iterdir())
    files = sorted(p for p in entries if p.is_file() and (p.name.endswith(".whl") or p.name.endswith(".tar.gz")))
    if len(files) != 2 or sum(p.name.endswith(".whl") for p in files) != 1 or sum(p.name.endswith(".tar.gz") for p in files) != 1:
        raise ValueError("artifact directory must contain exactly one wheel and one .tar.gz sdist")
    if any(item.name not in {p.name for p in files} | {"provenance.json"} or not item.is_file() for item in entries):
        raise ValueError("artifact directory contains unexpected files")
    for path in files:
        if path.name.endswith(".whl"):
            name, version, _build, tags = parse_wheel_filename(path.name)
            if tags != {Tag("py3", "none", "any")}:
                raise ValueError(f"{path.name}: wheel must be platform independent")
        else:
            name, version = parse_sdist_filename(path.name)
        if name != DIST_NAME or version != expected_version:
            raise ValueError(f"{path.name}: expected {DIST_NAME} {expected_version}")
        metadata = Parser().parsestr(_metadata(path), headersonly=True)
        if metadata.get_all("Name") != [DIST_NAME] or metadata.get_all("Version") != [str(expected_version)]:
            raise ValueError(f"{path.name}: metadata name/version mismatch")
        if metadata.get_all("Requires-Python") != [">=3.10"]:
            raise ValueError(f"{path.name}: missing or invalid Requires-Python")
        requirements = [Requirement(value) for value in metadata.get_all("Requires-Dist", [])]
        expected = {"cc1101": "==3.0.0", "spidev": "", "rpi-lgpio": ""}
        if len(requirements) != len(expected) or any(
            canonicalize_name(req.name) not in expected or req.marker is not None
            or req.url is not None or req.extras
            or str(req.specifier) != expected.get(canonicalize_name(req.name))
            for req in requirements
        ) or {canonicalize_name(req.name) for req in requirements} != set(expected):
            raise ValueError(f"{path.name}: runtime dependencies do not match expected contract")
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_artifacts(tag: str, source_dir=PROJECT_ROOT, output_dir="dist", commit=None):
    version = parse_release_tag(tag)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output directory must be empty")
    with tempfile.TemporaryDirectory(prefix="cc1101-release-") as temp:
        copied = Path(temp) / "source"
        shutil.copytree(source_dir, copied, ignore=shutil.ignore_patterns(".git", ".idea", ".agents", ".aws", ".codex", "__pycache__", "build", "dist", ".venv", "*.egg-info"))
        version_file = copied / "cc1101_transceiver" / "_version.py"
        version_file.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
        subprocess.run([sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(output)], cwd=copied, env=sanitized_environment(), check=True)
    files = validate_artifacts(tag, output)
    if commit is not None:
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
            raise ValueError("commit must be a full hexadecimal Git object ID")
        manifest = {"event_commit": commit.lower(), "tag": tag, "version": version,
                    "artifacts": {p.name: _sha256(p) for p in files}}
        (output / "provenance.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return files


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG"))
    parser.add_argument("--source", default=str(PROJECT_ROOT))
    parser.add_argument("--output", default="dist")
    parser.add_argument("--commit")
    args = parser.parse_args(argv)
    if not args.tag:
        parser.error("--tag or RELEASE_TAG is required")
    try:
        for artifact in build_artifacts(args.tag, args.source, args.output, args.commit):
            print(artifact)
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
